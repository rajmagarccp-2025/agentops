from uuid import uuid4

from platform_api.identity_models import AuditLog
from platform_api.identity_repository import AuditLogRepository
from platform_api.mcp.gateway import tool_registry
from platform_api.security import Principal


def test_tool_execution_audit_event_is_persisted() -> None:
    tenant_id = str(uuid4())
    principal = Principal(
        subject="audit-user",
        tenant_id=tenant_id,
        roles=frozenset({"ADMIN"}),
        permissions=frozenset({"tools:execute"}),
        email="audit-user@example.com",
        project_id="project-1",
        environment_id="env-prod",
    )

    execution = tool_registry.execute(
        "kubernetes.scale_deployment",
        {"namespace": "default", "deployment": "checkout-api", "replicas": 4},
        principal,
        request_id="req-audit-001",
        dry_run=True,
    )

    assert execution.status == "dry_run"
    assert execution.execution_id

    from platform_api.database import SessionLocal

    with SessionLocal() as db:
        stored = (
            db.query(AuditLog)
            .filter(AuditLog.resource_type == "tool_call")
            .filter(AuditLog.resource_id == execution.execution_id)
            .order_by(AuditLog.sequence_number.desc())
            .first()
        )

    assert stored is not None
    assert stored.organization_id == tenant_id
    assert stored.project_id == "project-1"
    assert stored.environment_id == "env-prod"
    assert stored.details["tool_name"] == "kubernetes.scale_deployment"
    assert stored.details["outcome"] == "dry_run"
    with SessionLocal() as db:
        chain = AuditLogRepository().verify_chain(db, tenant_id)
    assert chain["valid"] is True
    assert chain["verified_events"] >= 2
