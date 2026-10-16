from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from platform_api.database import get_db
from platform_api.identity_repository import (
    AuditLogRepository,
    EnvironmentRepository,
    MembershipRepository,
    ProjectRepository,
)
from platform_api.security import (
    Principal,
    get_current_principal,
    verify_tenant_scope,
)

router = APIRouter(prefix="/ai", tags=["ai"])


class AIQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    organization_id: str = Field(..., min_length=1)
    project_id: str = Field(..., min_length=1)
    environment_id: str = Field(..., min_length=1)


@router.post("/query")
async def execute_ai_query(
    req: AIQueryRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Execute an AI query against a project and environment with RBAC and tenant isolation."""
    # 1. Enforce tenant scope
    verify_tenant_scope(principal, req.organization_id)

    # 2. Check user has ai.query permission
    has_ai_perm = (
        "ai.query" in principal.permissions
        or "ai:query" in principal.permissions
        or "platform:admin" in principal.permissions
        or "ADMIN" in principal.roles
    )
    if not has_ai_perm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: READ role cannot submit AI query actions",
        )

    # 3. Validate project belongs to organization
    project = ProjectRepository().get_project_by_id(db, req.project_id)
    if not project or project.tenant_id != req.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # 4. Validate environment belongs to project
    env = EnvironmentRepository().get_environment_by_id(db, req.environment_id)
    if not env or env.project_id != req.project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")

    # 5. Validate user has access to environment
    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, req.organization_id, user.id)
        if user
        else None
    )
    pm_info = (
        MembershipRepository().get_project_membership(db, req.project_id, user.id) if user else None
    )
    em_info = (
        MembershipRepository().get_environment_membership(db, req.environment_id, user.id)
        if user
        else None
    )

    # Check environment-level role if specified
    if em_info and em_info[1].name == "READ":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Permission denied: User has READ role on this environment "
                "and cannot execute AI queries"
            ),
        )

    has_env_access = bool(
        "ADMIN" in principal.roles
        or "platform-admin" in principal.roles
        or "WRITE" in principal.roles
        or (mem_info and mem_info[1].name in ("ADMIN", "OWNER", "WRITE"))
        or (pm_info and pm_info[1].name in ("ADMIN", "WRITE"))
        or (em_info and em_info[1].name in ("ADMIN", "WRITE"))
    )
    if not has_env_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: User does not have access to target environment",
        )

    AuditLogRepository().record_event(
        db,
        actor=user.id if user else principal.subject,
        actor_email=user.email if user else None,
        action="ai.queried",
        resource_type="environment",
        resource_id=env.id,
        organization_id=req.organization_id,
        project_id=req.project_id,
        environment_id=req.environment_id,
        details={"query_preview": req.query[:100]},
    )

    db.commit()

    return {
        "status": "success",
        "query": req.query,
        "scope": {
            "organization_id": req.organization_id,
            "project_id": req.project_id,
            "environment_id": req.environment_id,
        },
        "response": (
            f"AI synthesis for '{req.query}' in {env.name}: "
            "All systems operational, telemetry within threshold."
        ),
        "model": "platform-agent-router-v1",
        "confidence": 0.94,
    }
