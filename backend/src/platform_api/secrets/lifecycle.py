from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from platform_api.database import SessionLocal
from platform_api.identity_repository import AuditLogRepository
from platform_api.observability import increment
from platform_api.secrets.models import Secret, SecretLifecycleEvent

logger = logging.getLogger("platform_api.secrets.lifecycle")


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def process_secret_lifecycle(now: datetime | None = None) -> dict[str, int]:
    timestamp = now or datetime.now(UTC)
    expired_count = 0
    rotation_due_count = 0
    with SessionLocal() as db:
        secrets = db.scalars(
            select(Secret).where(Secret.status == "active")
        ).all()
        audit = AuditLogRepository()
        for secret in secrets:
            expired = False
            if secret.expiration_date is not None:
                expires_at = _as_utc(secret.expiration_date)
                if expires_at <= timestamp:
                    secret.status = "expired"
                    secret.updated_at = timestamp
                    audit.record_event(
                        db,
                        actor="secret-lifecycle-worker",
                        action="secret.expired",
                        resource_type="secret",
                        resource_id=secret.id,
                        organization_id=secret.tenant_id,
                        project_id=secret.project_id,
                        environment_id=secret.environment_id,
                        details={"expiration_date": expires_at.isoformat()},
                    )
                    expired_count += 1
                    expired = True

            if expired:
                continue
            if secret.rotation_interval_days is None:
                continue
            rotation_base = _as_utc(secret.last_rotated_at or secret.created_at)
            due_at = rotation_base + timedelta(days=secret.rotation_interval_days)
            if due_at > timestamp:
                continue
            exists = db.scalar(
                select(SecretLifecycleEvent.id).where(
                    SecretLifecycleEvent.secret_id == secret.id,
                    SecretLifecycleEvent.event_type == "rotation_due",
                    SecretLifecycleEvent.due_at == due_at,
                )
            )
            if exists is not None:
                continue
            db.add(
                SecretLifecycleEvent(
                    secret_id=secret.id,
                    tenant_id=secret.tenant_id,
                    event_type="rotation_due",
                    due_at=due_at,
                    created_at=timestamp,
                )
            )
            audit.record_event(
                db,
                actor="secret-lifecycle-worker",
                action="secret.rotation_due",
                resource_type="secret",
                resource_id=secret.id,
                organization_id=secret.tenant_id,
                project_id=secret.project_id,
                environment_id=secret.environment_id,
                details={"due_at": due_at.isoformat()},
            )
            logger.warning(
                "Secret rotation is due: tenant_id=%s secret_id=%s due_at=%s",
                secret.tenant_id,
                secret.id,
                due_at.isoformat(),
            )
            rotation_due_count += 1
        db.commit()

    if expired_count:
        increment("secrets.expired", expired_count)
        logger.warning("Expired %d secrets that passed their expiry time", expired_count)
    if rotation_due_count:
        increment("secrets.rotation_due", rotation_due_count)
    return {"expired": expired_count, "rotation_due": rotation_due_count}


def archive_old_audit_events(
    *, retention_days: int, batch_size: int = 500, now: datetime | None = None
) -> int:
    if retention_days < 1:
        raise ValueError("retention_days must be at least one")
    cutoff = (now or datetime.now(UTC)) - timedelta(days=retention_days)
    total_archived = 0
    with SessionLocal() as db:
        repository = AuditLogRepository()
        while True:
            archived = repository.archive_before(db, cutoff, batch_size)
            total_archived += archived
            db.commit()
            if archived < batch_size:
                break
    if total_archived:
        increment("audit.events.archived", total_archived)
        logger.info(
            "Archived %d immutable audit events older than %d days",
            total_archived,
            retention_days,
        )
    return total_archived
