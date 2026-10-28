from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    delete,
    func,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from platform_api.config import get_settings
from platform_api.database import Base, SessionLocal
from platform_api.observability import increment, record_alert, redact_sensitive_value

logger = logging.getLogger("platform_api.workflow_queue")


class WorkflowJobStatus:
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


class WorkflowQueueFullError(RuntimeError):
    pass


class WorkflowJobRecord(Base):
    __tablename__ = "workflow_jobs"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=WorkflowJobStatus.PENDING, index=True
    )
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(default=3, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(default=600, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dead_lettered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class WorkflowWorkerHeartbeat(Base):
    __tablename__ = "workflow_worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    active_jobs: Mapped[int] = mapped_column(default=0, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class WorkflowOutboxRecord(Base):
    __tablename__ = "workflow_outbox"
    __table_args__ = (UniqueConstraint("job_id", "delivery_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delivery_number: Mapped[int] = mapped_column(nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


@dataclass(frozen=True)
class WorkflowOutboxMessage:
    id: str
    job_id: str
    delivery_number: int
    tenant_id: str
    correlation_id: str
    idempotency_key: str


class DurableWorkflowQueue:
    """Database-backed workflow queue with tenant-scoped idempotency and recoverable leases."""

    def enqueue(
        self,
        *,
        tenant_id: str,
        job_type: str,
        payload: dict[str, Any],
        run_id: str | None = None,
        idempotency_key: str | None = None,
        max_attempts: int = 3,
        timeout_seconds: int | None = None,
    ) -> WorkflowJobRecord:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if idempotency_key is not None and not 1 <= len(idempotency_key) <= 255:
            raise ValueError("idempotency_key must contain between 1 and 255 characters")
        settings = get_settings()
        timeout = timeout_seconds or settings.workflow_job_timeout_seconds

        with SessionLocal() as db:
            if idempotency_key:
                existing = self._find_by_idempotency(db, tenant_id, idempotency_key)
                if existing is not None:
                    existing_payload = {
                        key: value for key, value in existing.payload.items() if key != "run_id"
                    }
                    requested_payload = {
                        key: value for key, value in payload.items() if key != "run_id"
                    }
                    if existing_payload != requested_payload or existing.job_type != job_type:
                        raise ValueError("Idempotency key was already used for a different request")
                    return existing

            active_count = db.scalar(
                select(func.count()).where(
                    WorkflowJobRecord.status.in_(
                        [
                            WorkflowJobStatus.PENDING,
                            WorkflowJobStatus.RETRYING,
                            WorkflowJobStatus.RUNNING,
                        ]
                    )
                )
            )
            if active_count is not None and active_count >= settings.workflow_queue_max_pending:
                increment("workflow.queue.rejected")
                record_alert("workflow_queue_full", "critical")
                logger.critical(
                    "Workflow queue capacity reached: active_jobs=%s limit=%s",
                    active_count,
                    settings.workflow_queue_max_pending,
                )
                raise WorkflowQueueFullError("Workflow queue is at capacity")

            record = WorkflowJobRecord(
                tenant_id=tenant_id,
                run_id=run_id,
                idempotency_key=idempotency_key,
                job_type=job_type,
                status=WorkflowJobStatus.PENDING,
                attempts=0,
                max_attempts=max_attempts,
                timeout_seconds=timeout,
                payload=payload,
            )
            db.add(record)
            try:
                db.flush()
                if settings.workflow_queue_backend == "pubsub":
                    self._add_outbox_message(db, record, delivery_number=0)
                db.commit()
            except IntegrityError:
                db.rollback()
                if idempotency_key:
                    existing = self._find_by_idempotency(db, tenant_id, idempotency_key)
                    if existing is not None:
                        existing_payload = {
                            key: value for key, value in existing.payload.items() if key != "run_id"
                        }
                        requested_payload = {
                            key: value for key, value in payload.items() if key != "run_id"
                        }
                        if existing_payload == requested_payload and existing.job_type == job_type:
                            return existing
                raise
            db.refresh(record)
            increment("workflow.queue.enqueued")
            return record

    @staticmethod
    def _add_outbox_message(
        db: Session,
        job: WorkflowJobRecord,
        *,
        delivery_number: int,
        available_at: datetime | None = None,
    ) -> None:
        db.add(
            WorkflowOutboxRecord(
                job_id=job.id,
                delivery_number=delivery_number,
                tenant_id=job.tenant_id,
                correlation_id=job.run_id or job.id,
                idempotency_key=job.idempotency_key or job.id,
                available_at=available_at or datetime.now(UTC),
            )
        )

    def claim_outbox_messages(
        self, *, worker_id: str, limit: int = 20, lease_seconds: int = 60
    ) -> list[WorkflowOutboxMessage]:
        now = datetime.now(UTC)
        with SessionLocal() as db:
            records = list(
                db.scalars(
                    select(WorkflowOutboxRecord)
                    .where(
                        WorkflowOutboxRecord.available_at <= now,
                        (WorkflowOutboxRecord.status == "pending")
                        | (
                            (WorkflowOutboxRecord.status == "publishing")
                            & (WorkflowOutboxRecord.lease_expires_at <= now)
                        ),
                    )
                    .order_by(WorkflowOutboxRecord.created_at.asc())
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                ).all()
            )
            claimed: list[WorkflowOutboxMessage] = []
            for record in records:
                record.status = "publishing"
                record.attempts += 1
                record.lease_owner = worker_id
                record.lease_expires_at = now + timedelta(seconds=lease_seconds)
                claimed.append(
                    WorkflowOutboxMessage(
                        id=record.id,
                        job_id=record.job_id,
                        delivery_number=record.delivery_number,
                        tenant_id=record.tenant_id,
                        correlation_id=record.correlation_id,
                        idempotency_key=record.idempotency_key,
                    )
                )
            db.commit()
            return claimed

    def mark_outbox_published(self, message_id: str, *, worker_id: str) -> bool:
        with SessionLocal() as db:
            record = db.get(WorkflowOutboxRecord, message_id)
            if record is None or record.status != "publishing" or record.lease_owner != worker_id:
                return False
            record.status = "published"
            record.published_at = datetime.now(UTC)
            record.lease_owner = None
            record.lease_expires_at = None
            record.last_error = None
            db.commit()
            return True

    def retry_outbox_publish(self, message_id: str, *, worker_id: str, error: str) -> bool:
        with SessionLocal() as db:
            record = db.get(WorkflowOutboxRecord, message_id)
            if record is None or record.status != "publishing" or record.lease_owner != worker_id:
                return False
            record.status = "pending"
            record.available_at = datetime.now(UTC) + timedelta(
                seconds=min(300, 2 ** min(record.attempts, 8))
            )
            record.lease_owner = None
            record.lease_expires_at = None
            record.last_error = redact_sensitive_value(error)[:1000]
            db.commit()
            increment("workflow.outbox.publish_errors")
            return True

    def purge_published_outbox(self, *, retention_days: int = 30, batch_size: int = 500) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        terminal_statuses = [
            WorkflowJobStatus.SUCCEEDED,
            WorkflowJobStatus.FAILED,
            WorkflowJobStatus.DEAD_LETTER,
            WorkflowJobStatus.CANCELLED,
        ]
        with SessionLocal() as db:
            candidates = (
                select(WorkflowOutboxRecord.id)
                .join(WorkflowJobRecord, WorkflowJobRecord.id == WorkflowOutboxRecord.job_id)
                .where(
                    WorkflowOutboxRecord.status == "published",
                    WorkflowOutboxRecord.published_at < cutoff,
                    WorkflowJobRecord.status.in_(terminal_statuses),
                )
                .order_by(WorkflowOutboxRecord.published_at.asc())
                .limit(batch_size)
            )
            candidate_ids = list(db.scalars(candidates).all())
            if not candidate_ids:
                return 0
            db.execute(
                delete(WorkflowOutboxRecord).where(WorkflowOutboxRecord.id.in_(candidate_ids))
            )
            db.commit()
            return len(candidate_ids)

    def _find_by_idempotency(
        self, db: Session, tenant_id: str, idempotency_key: str
    ) -> WorkflowJobRecord | None:
        return db.scalar(
            select(WorkflowJobRecord).where(
                WorkflowJobRecord.tenant_id == tenant_id,
                WorkflowJobRecord.idempotency_key == idempotency_key,
            )
        )

    def claim_next(
        self,
        *,
        worker_id: str,
        tenant_id: str | None = None,
        lease_seconds: int | None = None,
    ) -> WorkflowJobRecord | None:
        now = datetime.now(UTC)
        lease = lease_seconds or get_settings().workflow_job_lease_seconds
        with SessionLocal() as db:
            self._recover_expired_leases(db, now)
            stmt = (
                select(WorkflowJobRecord)
                .where(
                    WorkflowJobRecord.status.in_(
                        [WorkflowJobStatus.PENDING, WorkflowJobStatus.RETRYING]
                    ),
                    WorkflowJobRecord.dead_lettered.is_(False),
                    WorkflowJobRecord.available_at <= now,
                )
                .order_by(WorkflowJobRecord.created_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if tenant_id:
                stmt = stmt.where(WorkflowJobRecord.tenant_id == tenant_id)
            candidate = db.scalar(stmt)
            if candidate is None:
                db.commit()
                return None
            result = db.execute(
                update(WorkflowJobRecord)
                .where(
                    WorkflowJobRecord.id == candidate.id,
                    WorkflowJobRecord.status.in_(
                        [WorkflowJobStatus.PENDING, WorkflowJobStatus.RETRYING]
                    ),
                    WorkflowJobRecord.available_at <= now,
                )
                .values(
                    status=WorkflowJobStatus.RUNNING,
                    attempts=WorkflowJobRecord.attempts + 1,
                    worker_id=worker_id,
                    lease_expires_at=now + timedelta(seconds=lease),
                    updated_at=now,
                )
                .returning(WorkflowJobRecord.id)
                .execution_options(synchronize_session=False)
            )
            claimed_id = result.scalar_one_or_none()
            result.close()
            if claimed_id is None:
                db.commit()
                return None
            db.commit()
            record = db.get(WorkflowJobRecord, claimed_id)
            if record is None:
                raise RuntimeError(f"Claimed workflow job {claimed_id} disappeared")
            db.refresh(record)
            increment("workflow.queue.claimed")
            return record

    def claim_by_id(self, job_id: str, *, worker_id: str) -> WorkflowJobRecord | None:
        now = datetime.now(UTC)
        with SessionLocal() as db:
            result = db.execute(
                update(WorkflowJobRecord)
                .where(
                    WorkflowJobRecord.id == job_id,
                    WorkflowJobRecord.status.in_(
                        [WorkflowJobStatus.PENDING, WorkflowJobStatus.RETRYING]
                    ),
                    WorkflowJobRecord.available_at <= now,
                )
                .values(
                    status=WorkflowJobStatus.RUNNING,
                    attempts=WorkflowJobRecord.attempts + 1,
                    worker_id=worker_id,
                    lease_expires_at=now
                    + timedelta(seconds=get_settings().workflow_job_lease_seconds),
                    updated_at=now,
                )
                .returning(WorkflowJobRecord.id)
                .execution_options(synchronize_session=False)
            )
            claimed_id = result.scalar_one_or_none()
            result.close()
            if claimed_id is None:
                db.commit()
                return None
            db.commit()
            record = db.get(WorkflowJobRecord, claimed_id)
            if record is None:
                raise RuntimeError(f"Claimed workflow job {claimed_id} disappeared")
            increment("workflow.queue.claimed")
            return record

    def _recover_expired_leases(self, db: Session, now: datetime) -> None:
        expired = list(
            db.scalars(
                select(WorkflowJobRecord).where(
                    WorkflowJobRecord.status == WorkflowJobStatus.RUNNING,
                    WorkflowJobRecord.lease_expires_at <= now,
                )
            ).all()
        )
        for record in expired:
            record.worker_id = None
            record.lease_expires_at = None
            record.updated_at = now
            if record.attempts >= record.max_attempts:
                record.status = WorkflowJobStatus.DEAD_LETTER
                record.dead_lettered = True
                record.error_message = "Worker lease expired after the maximum number of attempts"
                record.completed_at = now
                increment("workflow.queue.dead_lettered")
                record_alert("workflow_job_dead_lettered", "critical")
                logger.critical(
                    "Workflow job dead-lettered after expired lease: job_id=%s tenant_id=%s",
                    record.id,
                    record.tenant_id,
                )
            else:
                record.status = WorkflowJobStatus.RETRYING
                delay = min(300, 2 ** min(record.attempts, 8))
                record.available_at = now + timedelta(seconds=delay)
                record.error_message = "Worker lease expired; scheduled for retry"
                if get_settings().workflow_queue_backend == "pubsub":
                    self._add_outbox_message(
                        db,
                        record,
                        delivery_number=record.attempts,
                        available_at=record.available_at,
                    )
                increment("workflow.queue.lease_expired")
        if expired:
            db.flush()

    def mark_succeeded(
        self, job_id: str, *, result: dict[str, Any] | None = None
    ) -> WorkflowJobRecord:
        with SessionLocal() as db:
            record = db.get(WorkflowJobRecord, job_id)
            if record is None:
                raise KeyError(job_id)
            if record.status != WorkflowJobStatus.RUNNING:
                return record
            record.status = WorkflowJobStatus.SUCCEEDED
            record.result = result or {}
            record.error_message = None
            record.worker_id = None
            record.lease_expires_at = None
            record.completed_at = datetime.now(UTC)
            record.updated_at = datetime.now(UTC)
            db.commit()
            db.refresh(record)
            increment("workflow.queue.succeeded")
            return record

    def mark_failed(self, job_id: str, *, error: str, retryable: bool = True) -> WorkflowJobRecord:
        with SessionLocal() as db:
            record = db.get(WorkflowJobRecord, job_id)
            if record is None:
                raise KeyError(job_id)
            if record.status != WorkflowJobStatus.RUNNING:
                return record
            now = datetime.now(UTC)
            record.worker_id = None
            record.lease_expires_at = None
            record.error_message = redact_sensitive_value(error)[:4000]
            record.updated_at = now
            if retryable and record.attempts < record.max_attempts:
                record.status = WorkflowJobStatus.RETRYING
                record.available_at = now + timedelta(
                    seconds=min(300, 2 ** min(record.attempts, 8))
                )
                if get_settings().workflow_queue_backend == "pubsub":
                    self._add_outbox_message(
                        db,
                        record,
                        delivery_number=record.attempts,
                        available_at=record.available_at,
                    )
                increment("workflow.queue.retrying")
            else:
                record.status = WorkflowJobStatus.DEAD_LETTER
                record.dead_lettered = True
                record.completed_at = now
                increment("workflow.queue.dead_lettered")
                record_alert("workflow_job_dead_lettered", "critical")
                logger.critical(
                    "Workflow job dead-lettered after failed attempt: job_id=%s tenant_id=%s",
                    record.id,
                    record.tenant_id,
                )
            db.commit()
            db.refresh(record)
            return record

    def get(self, job_id: str) -> WorkflowJobRecord | None:
        with SessionLocal() as db:
            return db.get(WorkflowJobRecord, job_id)

    def cancel_run(self, run_id: str, *, tenant_id: str, reason: str) -> WorkflowJobRecord | None:
        with SessionLocal() as db:
            record = db.scalar(
                select(WorkflowJobRecord).where(
                    WorkflowJobRecord.run_id == run_id,
                    WorkflowJobRecord.tenant_id == tenant_id,
                )
            )
            if record is None:
                return None
            if record.status in {
                WorkflowJobStatus.SUCCEEDED,
                WorkflowJobStatus.FAILED,
                WorkflowJobStatus.DEAD_LETTER,
                WorkflowJobStatus.CANCELLED,
            }:
                return record
            now = datetime.now(UTC)
            record.status = WorkflowJobStatus.CANCELLED
            record.error_message = redact_sensitive_value(reason)[:4000]
            record.completed_at = now
            record.updated_at = now
            record.lease_expires_at = None
            db.commit()
            db.refresh(record)
            increment("workflow.queue.cancelled")
            return record

    def replay_dead_letter(
        self,
        run_id: str,
        *,
        tenant_id: str,
        actor: str,
        actor_email: str | None,
    ) -> WorkflowJobRecord | None:
        with SessionLocal() as db:
            record = db.scalar(
                select(WorkflowJobRecord)
                .where(
                    WorkflowJobRecord.run_id == run_id,
                    WorkflowJobRecord.tenant_id == tenant_id,
                )
                .with_for_update()
            )
            if record is None:
                return None
            if record.status != WorkflowJobStatus.DEAD_LETTER:
                raise ValueError("Only dead-lettered workflow jobs can be replayed")

            now = datetime.now(UTC)
            record.status = WorkflowJobStatus.PENDING
            record.attempts = 0
            record.dead_lettered = False
            record.available_at = now
            record.completed_at = None
            record.worker_id = None
            record.lease_expires_at = None
            record.result = None
            record.updated_at = now

            if get_settings().workflow_queue_backend == "pubsub":
                previous_delivery = db.scalar(
                    select(func.max(WorkflowOutboxRecord.delivery_number)).where(
                        WorkflowOutboxRecord.job_id == record.id
                    )
                )
                self._add_outbox_message(
                    db,
                    record,
                    delivery_number=(previous_delivery or 0) + 1,
                    available_at=now,
                )

            from platform_api.identity_repository import AuditLogRepository

            AuditLogRepository().record_event(
                db,
                actor=actor,
                actor_email=actor_email,
                action="workflow.dead_letter_replayed",
                resource_type="workflow_job",
                resource_id=record.id,
                organization_id=record.tenant_id,
                details={"run_id": run_id, "job_type": record.job_type},
            )
            db.commit()
            db.refresh(record)
            increment("workflow.queue.replayed")
            return record

    def list_pending(self, tenant_id: str | None = None) -> list[WorkflowJobRecord]:
        with SessionLocal() as db:
            stmt = select(WorkflowJobRecord).where(
                WorkflowJobRecord.status.in_(
                    [
                        WorkflowJobStatus.PENDING,
                        WorkflowJobStatus.RETRYING,
                        WorkflowJobStatus.RUNNING,
                    ]
                )
            )
            if tenant_id:
                stmt = stmt.where(WorkflowJobRecord.tenant_id == tenant_id)
            return list(db.scalars(stmt.order_by(WorkflowJobRecord.created_at.asc())).all())

    def summary(self) -> dict[str, int]:
        with SessionLocal() as db:
            rows = db.execute(
                select(WorkflowJobRecord.status, func.count()).group_by(WorkflowJobRecord.status)
            )
            return {status: count for status, count in rows}

    def record_worker_heartbeat(self, *, worker_id: str, status: str, active_jobs: int) -> None:
        now = datetime.now(UTC)
        with SessionLocal() as db:
            record = db.get(WorkflowWorkerHeartbeat, worker_id)
            if record is None:
                record = WorkflowWorkerHeartbeat(
                    worker_id=worker_id,
                    status=status,
                    active_jobs=active_jobs,
                    last_seen_at=now,
                )
                db.add(record)
            else:
                record.status = status
                record.active_jobs = active_jobs
                record.last_seen_at = now
            db.commit()

    def worker_summary(self, *, stale_after_seconds: int = 60) -> dict[str, int]:
        cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
        with SessionLocal() as db:
            workers = db.scalars(
                select(WorkflowWorkerHeartbeat).where(
                    WorkflowWorkerHeartbeat.last_seen_at >= cutoff
                )
            ).all()
            return {
                "workers_online": sum(worker.status == "running" for worker in workers),
                "worker_active_jobs": sum(worker.active_jobs for worker in workers),
            }


class WorkflowQueuePort(Protocol):
    def enqueue(
        self,
        *,
        tenant_id: str,
        job_type: str,
        payload: dict[str, Any],
        run_id: str | None = None,
        idempotency_key: str | None = None,
        max_attempts: int = 3,
        timeout_seconds: int | None = None,
    ) -> WorkflowJobRecord: ...

    def claim_next(
        self,
        *,
        worker_id: str,
        tenant_id: str | None = None,
        lease_seconds: int | None = None,
    ) -> WorkflowJobRecord | None: ...

    def claim_by_id(self, job_id: str, *, worker_id: str) -> WorkflowJobRecord | None: ...

    def get(self, job_id: str) -> WorkflowJobRecord | None: ...

    def mark_succeeded(
        self, job_id: str, *, result: dict[str, Any] | None = None
    ) -> WorkflowJobRecord: ...

    def mark_failed(
        self, job_id: str, *, error: str, retryable: bool = True
    ) -> WorkflowJobRecord: ...

    def cancel_run(
        self, run_id: str, *, tenant_id: str, reason: str
    ) -> WorkflowJobRecord | None: ...

    def replay_dead_letter(
        self,
        run_id: str,
        *,
        tenant_id: str,
        actor: str,
        actor_email: str | None,
    ) -> WorkflowJobRecord | None: ...

    def claim_outbox_messages(
        self, *, worker_id: str, limit: int = 20, lease_seconds: int = 60
    ) -> list[WorkflowOutboxMessage]: ...

    def mark_outbox_published(self, message_id: str, *, worker_id: str) -> bool: ...

    def retry_outbox_publish(self, message_id: str, *, worker_id: str, error: str) -> bool: ...

    def purge_published_outbox(self, *, retention_days: int = 30, batch_size: int = 500) -> int: ...

    def record_worker_heartbeat(self, *, worker_id: str, status: str, active_jobs: int) -> None: ...

    def worker_summary(self, *, stale_after_seconds: int = 60) -> dict[str, int]: ...

    def list_pending(self, tenant_id: str | None = None) -> list[WorkflowJobRecord]: ...

    def summary(self) -> dict[str, int]: ...


workflow_queue: WorkflowQueuePort = DurableWorkflowQueue()
