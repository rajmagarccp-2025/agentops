from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from platform_api.workflow_queue import (
    WorkflowJobStatus,
    workflow_queue,
)


def test_queue_idempotency_is_tenant_scoped_and_payload_bound() -> None:
    tenant_id = str(uuid4())
    first = workflow_queue.enqueue(
        tenant_id=tenant_id,
        job_type="agent_run",
        payload={"request": "inspect"},
        idempotency_key="request-1",
    )
    repeated = workflow_queue.enqueue(
        tenant_id=tenant_id,
        job_type="agent_run",
        payload={"request": "inspect"},
        idempotency_key="request-1",
    )
    assert repeated.id == first.id

    with pytest.raises(ValueError, match="different request"):
        workflow_queue.enqueue(
            tenant_id=tenant_id,
            job_type="agent_run",
            payload={"request": "modify"},
            idempotency_key="request-1",
        )

    another_tenant = workflow_queue.enqueue(
        tenant_id=str(uuid4()),
        job_type="agent_run",
        payload={"request": "inspect"},
        idempotency_key="request-1",
    )
    assert another_tenant.id != first.id


def test_queue_retry_and_dead_letter_are_bounded() -> None:
    job = workflow_queue.enqueue(
        tenant_id=str(uuid4()),
        job_type="agent_run",
        payload={"retry_safe": True},
        max_attempts=2,
    )
    claimed = workflow_queue.claim_by_id(job.id, worker_id="queue-test")
    assert claimed is not None
    first_failure = workflow_queue.mark_failed(job.id, error="temporary failure")
    assert first_failure.status == WorkflowJobStatus.RETRYING
    available_at = first_failure.available_at
    if available_at.tzinfo is None:
        available_at = available_at.replace(tzinfo=UTC)
    assert available_at > datetime.now(UTC)

    from platform_api.database import SessionLocal
    from platform_api.workflow_queue import WorkflowJobRecord

    with SessionLocal() as db:
        record = db.get(WorkflowJobRecord, job.id)
        assert record is not None
        record.available_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    second_claim = workflow_queue.claim_by_id(job.id, worker_id="queue-test")
    assert second_claim is not None
    dead_letter = workflow_queue.mark_failed(job.id, error="retry exhausted")
    assert dead_letter.status == WorkflowJobStatus.DEAD_LETTER
    assert dead_letter.dead_lettered is True


def test_expired_worker_lease_is_recovered_to_retry() -> None:
    job = workflow_queue.enqueue(
        tenant_id=str(uuid4()),
        job_type="agent_run",
        payload={"retry_safe": True},
        max_attempts=2,
    )
    assert workflow_queue.claim_by_id(job.id, worker_id="lease-test") is not None

    from platform_api.database import SessionLocal
    from platform_api.workflow_queue import WorkflowJobRecord

    with SessionLocal() as db:
        record = db.get(WorkflowJobRecord, job.id)
        assert record is not None
        record.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    workflow_queue.claim_next(worker_id="lease-recovery-test")
    recovered = workflow_queue.get(job.id)
    assert recovered is not None
    assert recovered.status == WorkflowJobStatus.RETRYING
    assert recovered.worker_id is None


def test_queued_run_cancellation_is_terminal() -> None:
    tenant_id = str(uuid4())
    job = workflow_queue.enqueue(
        tenant_id=tenant_id,
        job_type="agent_run",
        payload={"request": "inspect"},
        run_id=str(uuid4()),
    )
    cancelled = workflow_queue.cancel_run(
        job.run_id or "",
        tenant_id=tenant_id,
        reason="operator requested cancellation",
    )
    assert cancelled is not None
    assert cancelled.status == WorkflowJobStatus.CANCELLED
    assert workflow_queue.mark_succeeded(job.id).status == WorkflowJobStatus.CANCELLED
