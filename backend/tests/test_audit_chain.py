from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from platform_api.database import SessionLocal
from platform_api.identity_models import AuditLog, AuditLogArchive
from platform_api.identity_repository import AuditLogRepository


def test_audit_events_form_a_verifiable_tenant_chain() -> None:
    tenant_id = str(uuid4())
    repository = AuditLogRepository()
    with SessionLocal() as db:
        repository.record_event(
            db,
            actor="audit-test",
            action="workflow.started",
            resource_type="workflow",
            resource_id=str(uuid4()),
            organization_id=tenant_id,
            details={"status": "queued"},
        )
        repository.record_event(
            db,
            actor="audit-test",
            action="workflow.completed",
            resource_type="workflow",
            resource_id=str(uuid4()),
            organization_id=tenant_id,
            details={"status": "completed"},
        )
        db.commit()

        valid = repository.verify_chain(db, tenant_id)
        assert valid["valid"] is True
        assert valid["verified_events"] == 2

        row = db.scalar(
            select(AuditLog).where(
                AuditLog.organization_id == tenant_id,
                AuditLog.sequence_number == 1,
            )
        )
        assert row is not None
        row.details = {"status": "tampered"}
        with pytest.raises(IntegrityError, match="append-only"):
            db.commit()
        db.rollback()
        assert repository.verify_chain(db, tenant_id)["valid"] is True


def test_old_audit_events_are_copied_to_immutable_archive() -> None:
    tenant_id = str(uuid4())
    repository = AuditLogRepository()
    with SessionLocal() as db:
        event = repository.record_event(
            db,
            actor="archive-test",
            action="retention.test",
            resource_type="test",
            resource_id=str(uuid4()),
            organization_id=tenant_id,
        )
        db.commit()

        archived = repository.archive_before(db, datetime.now(UTC) + timedelta(seconds=1))
        db.commit()
        assert archived >= 1
        assert db.get(AuditLogArchive, event.id) is not None
        assert repository.verify_chain(db, tenant_id)["valid"] is True
