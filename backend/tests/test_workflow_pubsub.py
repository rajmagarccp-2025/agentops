from __future__ import annotations

from concurrent.futures import Future
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from platform_api.config import get_settings
from platform_api.worker import BackgroundWorker
from platform_api.workflow_pubsub import (
    PubSubWorkflowTransport,
    PulledWorkflowMessage,
    WorkflowDispatchMessage,
    parse_dispatch_message,
)
from platform_api.workflow_queue import (
    WorkflowJobRecord,
    WorkflowJobStatus,
    WorkflowOutboxRecord,
    WorkflowWorkerHeartbeat,
    workflow_queue,
)


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes]] = []

    def topic_path(self, project_id: str, topic_id: str) -> str:
        return f"projects/{project_id}/topics/{topic_id}"

    def publish(self, topic: str, data: bytes) -> Future[str]:
        self.published.append((topic, data))
        future: Future[str] = Future()
        future.set_result("server-message-id")
        return future

    def stop(self) -> None:
        return None


class FakeSubscriber:
    def __init__(self) -> None:
        self.acknowledged: list[str] = []
        self.modified_deadlines: list[tuple[str, int]] = []

    def subscription_path(self, project_id: str, subscription_id: str) -> str:
        return f"projects/{project_id}/subscriptions/{subscription_id}"

    def pull(self, *, request: dict[str, object], timeout: float) -> SimpleNamespace:
        return SimpleNamespace(received_messages=[])

    def acknowledge(self, *, request: dict[str, object]) -> None:
        ack_ids = request.get("ack_ids")
        if isinstance(ack_ids, list):
            self.acknowledged.extend(ack_id for ack_id in ack_ids if isinstance(ack_id, str))

    def modify_ack_deadline(self, *, request: dict[str, object]) -> None:
        ack_ids = request.get("ack_ids")
        seconds = request.get("ack_deadline_seconds")
        if isinstance(ack_ids, list) and ack_ids and isinstance(ack_ids[0], str):
            if isinstance(seconds, int):
                self.modified_deadlines.append((ack_ids[0], seconds))

    def close(self) -> None:
        return None


class FakeDeliveryTransport:
    def __init__(self) -> None:
        self.acknowledged: list[str] = []
        self.rejected: list[str] = []

    def acknowledge(self, ack_id: str) -> None:
        self.acknowledged.append(ack_id)

    def negative_acknowledge(self, ack_id: str) -> None:
        self.rejected.append(ack_id)

    def extend_ack_deadline(self, ack_id: str, seconds: int) -> None:
        return None


def _install_isolated_queue_db(
    monkeypatch: pytest.MonkeyPatch,
    *,
    backend: str = "database",
) -> sessionmaker:
    from platform_api import workflow_queue as queue_module
    from platform_api.database import Base
    from platform_api.identity_models import AuditChainHead, AuditLog

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            WorkflowJobRecord.__table__,
            WorkflowWorkerHeartbeat.__table__,
            WorkflowOutboxRecord.__table__,
            AuditChainHead.__table__,
            AuditLog.__table__,
        ],
    )
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    test_settings = get_settings().model_copy(update={"workflow_queue_backend": backend})
    monkeypatch.setattr(queue_module, "SessionLocal", session_factory)
    monkeypatch.setattr(queue_module, "get_settings", lambda: test_settings)
    return session_factory


def test_pubsub_dispatch_contains_only_stable_job_identifiers() -> None:
    message = WorkflowDispatchMessage(
        message_id=str(uuid4()),
        job_id=str(uuid4()),
        tenant_id=str(uuid4()),
        correlation_id=str(uuid4()),
        idempotency_key="request-42",
    )

    encoded = message.model_dump_json()
    parsed = parse_dispatch_message(encoded.encode())

    assert parsed == message
    assert "secret_value" not in encoded
    assert "credential" not in encoded


def test_pubsub_dispatch_rejects_unknown_fields_and_versions() -> None:
    with pytest.raises(ValidationError):
        parse_dispatch_message(
            b'{"schema_version":2,"message_id":"m","job_id":"j","tenant_id":"t",'
            b'"correlation_id":"c","idempotency_key":"i"}'
        )
    with pytest.raises(ValidationError):
        parse_dispatch_message(
            b'{"schema_version":1,"message_id":"m","job_id":"j","tenant_id":"t",'
            b'"correlation_id":"c","idempotency_key":"i","payload":{"secret":"value"}}'
        )


def test_pubsub_transport_uses_configured_resource_paths() -> None:
    publisher = FakePublisher()
    subscriber = FakeSubscriber()
    transport = PubSubWorkflowTransport(
        publisher,
        subscriber,
        project_id="test-project",
        topic_id="jobs",
        subscription_id="jobs-sub",
    )
    message = WorkflowDispatchMessage(
        message_id="outbox-1",
        job_id="job-1",
        tenant_id="tenant-1",
        correlation_id="run-1",
        idempotency_key="request-1",
    )

    transport.publish(message)
    transport.acknowledge("ack-1")
    transport.extend_ack_deadline("ack-2", 60)

    assert publisher.published[0][0] == "projects/test-project/topics/jobs"
    assert parse_dispatch_message(publisher.published[0][1]) == message
    assert subscriber.acknowledged == ["ack-1"]
    assert subscriber.modified_deadlines == [("ack-2", 60)]


def test_pubsub_outbox_is_transactional_and_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_isolated_queue_db(monkeypatch, backend="pubsub")
    tenant_id = str(uuid4())
    job = workflow_queue.enqueue(
        tenant_id=tenant_id,
        job_type="agent_run",
        payload={"request": "inspect"},
        run_id=str(uuid4()),
        idempotency_key=f"request-{uuid4()}",
    )
    repeated = workflow_queue.enqueue(
        tenant_id=tenant_id,
        job_type="agent_run",
        payload={"request": "inspect"},
        run_id=str(uuid4()),
        idempotency_key=job.idempotency_key,
    )

    assert repeated.id == job.id
    claimed = workflow_queue.claim_outbox_messages(worker_id="pubsub-test")
    assert len(claimed) == 1
    assert claimed[0].job_id == job.id
    assert claimed[0].tenant_id == tenant_id
    assert workflow_queue.mark_outbox_published(claimed[0].id, worker_id="pubsub-test")
    assert workflow_queue.claim_outbox_messages(worker_id="pubsub-test") == []


def test_pubsub_retry_creates_a_new_outbox_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory = _install_isolated_queue_db(monkeypatch, backend="pubsub")
    job = workflow_queue.enqueue(
        tenant_id=str(uuid4()),
        job_type="agent_run",
        payload={"retry_safe": True},
        max_attempts=2,
    )
    assert workflow_queue.claim_by_id(job.id, worker_id="pubsub-retry-test") is not None
    retrying = workflow_queue.mark_failed(job.id, error="temporary", retryable=True)
    assert retrying.status == WorkflowJobStatus.RETRYING

    with session_factory() as db:
        outbox = (
            db.query(WorkflowOutboxRecord)
            .filter(WorkflowOutboxRecord.job_id == job.id)
            .order_by(WorkflowOutboxRecord.delivery_number)
            .all()
        )

    assert [entry.delivery_number for entry in outbox] == [0, 1]


def test_pubsub_outbox_recovers_after_publish_failure_and_worker_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = _install_isolated_queue_db(monkeypatch, backend="pubsub")
    job = workflow_queue.enqueue(
        tenant_id=str(uuid4()),
        job_type="agent_run",
        payload={"request": "inspect"},
    )
    first_claim = workflow_queue.claim_outbox_messages(worker_id="publisher-1")[0]
    assert workflow_queue.retry_outbox_publish(
        first_claim.id,
        worker_id="publisher-1",
        error="password=supersecret",
    )
    with session_factory() as db:
        outbox = db.get(WorkflowOutboxRecord, first_claim.id)
        assert outbox is not None
        assert outbox.status == "pending"
        assert "supersecret" not in (outbox.last_error or "")
        outbox.available_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    retry_claim = workflow_queue.claim_outbox_messages(worker_id="publisher-after-restart")

    assert len(retry_claim) == 1
    assert retry_claim[0].job_id == job.id
    assert retry_claim[0].id == first_claim.id


def test_duplicate_pubsub_deliveries_cannot_claim_a_running_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_isolated_queue_db(monkeypatch)
    job = workflow_queue.enqueue(
        tenant_id=str(uuid4()),
        job_type="agent_run",
        payload={"request": "inspect"},
    )

    first_claim = workflow_queue.claim_by_id(job.id, worker_id="first-delivery")
    duplicate_claim = workflow_queue.claim_by_id(job.id, worker_id="duplicate-delivery")

    assert first_claim is not None
    assert duplicate_claim is None
    assert workflow_queue.get(job.id).attempts == 1


@pytest.mark.asyncio
async def test_worker_validates_tenant_and_acknowledges_after_durable_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import platform_api.workflow_queue as queue_module

    tenant_id = str(uuid4())
    job = SimpleNamespace(
        id=str(uuid4()),
        tenant_id=tenant_id,
        idempotency_key="request-1",
        status=WorkflowJobStatus.PENDING,
    )
    worker = BackgroundWorker.__new__(BackgroundWorker)
    worker.settings = get_settings().model_copy(
        update={"workflow_pubsub_ack_extension_seconds": 30}
    )
    worker.worker_id = "pubsub-worker-test"
    worker._pubsub_transport = FakeDeliveryTransport()
    monkeypatch.setattr(queue_module.workflow_queue, "get", lambda job_id: job)
    monkeypatch.setattr(queue_module.workflow_queue, "claim_by_id", lambda *args, **kwargs: job)

    async def execute_job(claimed_job: object) -> None:
        job.status = WorkflowJobStatus.SUCCEEDED

    monkeypatch.setattr(worker, "_execute_job", execute_job)
    payload = WorkflowDispatchMessage(
        message_id=str(uuid4()),
        job_id=job.id,
        tenant_id=tenant_id,
        correlation_id=str(uuid4()),
        idempotency_key=job.idempotency_key,
    )
    message = PulledWorkflowMessage(
        ack_id="ack-valid",
        data=payload.model_dump_json().encode(),
        pubsub_message_id="pubsub-valid",
    )

    await worker._handle_pubsub_delivery(message)

    assert worker._pubsub_transport.acknowledged == ["ack-valid"]
    assert worker._pubsub_transport.rejected == []


@pytest.mark.asyncio
async def test_worker_rejects_tenant_mismatched_pubsub_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import platform_api.workflow_queue as queue_module

    job = SimpleNamespace(
        id=str(uuid4()),
        tenant_id=str(uuid4()),
        idempotency_key="request-1",
        status=WorkflowJobStatus.PENDING,
    )
    worker = BackgroundWorker.__new__(BackgroundWorker)
    worker.settings = get_settings()
    worker.worker_id = "pubsub-worker-test"
    worker._pubsub_transport = FakeDeliveryTransport()
    monkeypatch.setattr(queue_module.workflow_queue, "get", lambda job_id: job)

    def unexpected_claim(*args: object, **kwargs: object) -> None:
        pytest.fail("Tenant-mismatched dispatch must not claim the job")

    monkeypatch.setattr(queue_module.workflow_queue, "claim_by_id", unexpected_claim)
    payload = WorkflowDispatchMessage(
        message_id=str(uuid4()),
        job_id=job.id,
        tenant_id=str(uuid4()),
        correlation_id=str(uuid4()),
        idempotency_key=job.idempotency_key,
    )
    message = PulledWorkflowMessage(
        ack_id="ack-invalid",
        data=payload.model_dump_json().encode(),
        pubsub_message_id="pubsub-invalid",
    )

    await worker._handle_pubsub_delivery(message)

    assert worker._pubsub_transport.acknowledged == []
    assert worker._pubsub_transport.rejected == ["ack-invalid"]


def test_dead_letter_replay_is_tenant_scoped_audited_and_republished(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = _install_isolated_queue_db(monkeypatch, backend="pubsub")
    from platform_api.identity_models import AuditLog

    job = workflow_queue.enqueue(
        tenant_id=str(uuid4()),
        job_type="agent_run",
        payload={"request": "inspect"},
        run_id=str(uuid4()),
        max_attempts=1,
    )
    with session_factory() as db:
        db_job = db.get(WorkflowJobRecord, job.id)
        if db_job is not None:
            db_job.available_at = datetime.now(UTC) - timedelta(minutes=1)
            db.commit()
    initial_delivery = workflow_queue.claim_outbox_messages(worker_id="dead-letter-test")[0]
    workflow_queue.mark_outbox_published(
        initial_delivery.id,
        worker_id="dead-letter-test",
    )
    pending = workflow_queue.get(job.id)
    assert pending is not None
    assert pending.status == WorkflowJobStatus.PENDING
    claimed = workflow_queue.claim_by_id(job.id, worker_id="dead-letter-test")
    assert claimed is not None, f"status={pending.status}, available_at={pending.available_at!r}"
    dead_letter = workflow_queue.mark_failed(job.id, error="terminal failure", retryable=False)
    assert dead_letter.status == WorkflowJobStatus.DEAD_LETTER

    assert (
        workflow_queue.replay_dead_letter(
            job.run_id or "",
            tenant_id=str(uuid4()),
            actor="other-tenant",
            actor_email=None,
        )
        is None
    )
    replayed = workflow_queue.replay_dead_letter(
        job.run_id or "",
        tenant_id=job.tenant_id,
        actor="operator-1",
        actor_email="operator@example.test",
    )

    assert replayed is not None
    assert replayed.status == WorkflowJobStatus.PENDING
    assert not replayed.dead_lettered
    with session_factory() as db:
        deliveries = (
            db.query(WorkflowOutboxRecord)
            .filter(WorkflowOutboxRecord.job_id == job.id)
            .order_by(WorkflowOutboxRecord.delivery_number)
            .all()
        )
        audit_event = (
            db.query(AuditLog)
            .filter(AuditLog.action == "workflow.dead_letter_replayed")
            .order_by(AuditLog.created_at.desc())
            .first()
        )
    assert [entry.delivery_number for entry in deliveries] == [0, 1]
    assert audit_event is not None
    assert audit_event.resource_id == job.id
