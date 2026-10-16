from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from platform_api.database import get_db
from platform_api.identity_repository import AuditLogRepository
from platform_api.security import (
    Principal,
    get_current_principal,
    require_permission,
    verify_tenant_scope,
)

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("")
async def list_audit_logs(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    organization_id: str | None = Query(None),
    project_id: str | None = Query(None),
    environment_id: str | None = Query(None),
    limit: int = Query(50, le=100),
) -> list[dict[str, Any]]:
    target_org = organization_id or principal.tenant_id
    if target_org:
        verify_tenant_scope(principal, target_org)

    logs = AuditLogRepository().list_logs(
        db,
        organization_id=target_org,
        project_id=project_id,
        environment_id=environment_id,
        limit=limit,
    )

    return [
        {
            "id": log.id,
            "actor": log.actor,
            "actor_email": log.actor_email,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "organization_id": log.organization_id,
            "project_id": log.project_id,
            "environment_id": log.environment_id,
            "details": log.details,
            "created_at": log.created_at.isoformat(),
            "sequence_number": log.sequence_number,
            "previous_hash": log.previous_hash,
            "event_hash": log.event_hash,
        }
        for log in logs
    ]


@router.get("/verify")
async def verify_audit_chain(
    principal: Annotated[Principal, Depends(require_permission("audit.read"))],
    db: Annotated[Session, Depends(get_db)],
    organization_id: str | None = Query(None),
) -> dict[str, Any]:
    target_org = organization_id or principal.tenant_id
    if target_org:
        verify_tenant_scope(principal, target_org)
    return AuditLogRepository().verify_chain(db, target_org)
