import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
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

router = APIRouter(tags=["environments"])


class EnvironmentCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: str | None = Field(None, max_length=100)
    type: str = Field("Development", pattern="^(Development|QA|Staging|Production|UAT|Custom)$")
    description: str = Field("", max_length=500)


class EnvironmentUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    type: str | None = Field(None, pattern="^(Development|QA|Staging|Production|UAT|Custom)$")
    description: str | None = Field(None, max_length=500)


class EnvironmentMemberRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    role: str = Field(..., pattern="^(ADMIN|WRITE|READ)$")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", slug)


@router.get("/projects/{project_id}/environments")
async def list_environments(
    project_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    project = ProjectRepository().get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    verify_tenant_scope(principal, project.tenant_id)

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, project.tenant_id, user.id)
        if user
        else None
    )
    pm_info = (
        MembershipRepository().get_project_membership(db, project.id, user.id) if user else None
    )

    is_admin = bool(
        (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
        or (pm_info and pm_info[1].name == "ADMIN")
        or "platform-admin" in principal.roles
    )

    envs = EnvironmentRepository().list_user_environments(
        db, project.tenant_id, project.id, user.id if user else "", is_proj_admin=is_admin
    )
    result = []
    for e in envs:
        em_info = (
            MembershipRepository().get_environment_membership(db, e.id, user.id) if user else None
        )
        env_role = (
            em_info[1].name
            if em_info
            else (pm_info[1].name if pm_info else (mem_info[1].name if mem_info else "READ"))
        )
        result.append(
            {
                "id": e.id,
                "project_id": e.project_id,
                "organization_id": e.tenant_id,
                "name": e.name,
                "slug": e.slug,
                "type": e.type,
                "description": e.description,
                "role": env_role,
                "can_delete": bool(
                    (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
                    or (pm_info and pm_info[1].name == "ADMIN")
                    or "platform-admin" in principal.roles
                ),
                "created_at": e.created_at.isoformat(),
            }
        )
    return result


@router.post("/projects/{project_id}/environments", status_code=status.HTTP_201_CREATED)
async def create_environment(
    project_id: str,
    req: EnvironmentCreateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project = ProjectRepository().get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    verify_tenant_scope(principal, project.tenant_id)

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, project.tenant_id, user.id)
        if user
        else None
    )
    pm_info = (
        MembershipRepository().get_project_membership(db, project.id, user.id) if user else None
    )

    can_create = bool(
        (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
        or (pm_info and pm_info[1].name in ("ADMIN", "WRITE"))
        or "platform-admin" in principal.roles
        or "environment.create" in principal.permissions
    )
    if not can_create:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Cannot create environments in this project",
        )

    slug = req.slug or _slugify(req.name)
    envs = EnvironmentRepository().list_environments(db, project.tenant_id, project.id)
    if any(e.slug == slug for e in envs):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Environment with slug '{slug}' already exists in this project",
        )

    env = EnvironmentRepository().create_environment(
        db,
        tenant_id=project.tenant_id,
        project_id=project.id,
        name=req.name,
        slug=slug,
        env_type=req.type,
        description=req.description,
    )

    if user:
        MembershipRepository().add_environment_member(db, env.id, user.id, "ADMIN")

    AuditLogRepository().record_event(
        db,
        actor=user.id if user else principal.subject,
        actor_email=user.email if user else None,
        action="environment.created",
        resource_type="environment",
        resource_id=env.id,
        organization_id=project.tenant_id,
        project_id=project.id,
        environment_id=env.id,
        details={"name": env.name, "type": env.type},
    )

    db.commit()

    return {
        "id": env.id,
        "project_id": env.project_id,
        "organization_id": env.tenant_id,
        "name": env.name,
        "slug": env.slug,
        "type": env.type,
        "description": env.description,
        "created_at": env.created_at.isoformat(),
    }


@router.get("/environments/{environment_id}")
async def get_environment(
    environment_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    env = EnvironmentRepository().get_environment_by_id(db, environment_id)
    if not env:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")

    verify_tenant_scope(principal, env.tenant_id)

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, env.tenant_id, user.id)
        if user
        else None
    )
    pm_info = (
        MembershipRepository().get_project_membership(db, env.project_id, user.id) if user else None
    )
    em_info = (
        MembershipRepository().get_environment_membership(db, env.id, user.id) if user else None
    )

    # Environment-level authorization check: Do not leak whether unauthorized resources exist
    has_access = bool(
        (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
        or (pm_info and pm_info[1].name == "ADMIN")
        or em_info
        or (pm_info and not em_info)  # Inherited project access if not restricted
        or "platform-admin" in principal.roles
    )
    if not has_access:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")

    role_name = em_info[1].name if em_info else (pm_info[1].name if pm_info else "READ")

    return {
        "id": env.id,
        "project_id": env.project_id,
        "organization_id": env.tenant_id,
        "name": env.name,
        "slug": env.slug,
        "type": env.type,
        "description": env.description,
        "role": role_name,
        "created_at": env.created_at.isoformat(),
    }


@router.get("/projects/{project_id}/environments/{environment_id}")
async def get_project_environment(
    project_id: str,
    environment_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    project = ProjectRepository().get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    verify_tenant_scope(principal, project.tenant_id)

    env = EnvironmentRepository().get_environment_by_id(db, environment_id)
    if not env or env.project_id != project.id or env.tenant_id != project.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found in this project"
        )

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, env.tenant_id, user.id)
        if user
        else None
    )
    pm_info = (
        MembershipRepository().get_project_membership(db, env.project_id, user.id) if user else None
    )
    em_info = (
        MembershipRepository().get_environment_membership(db, env.id, user.id) if user else None
    )

    has_access = bool(
        (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
        or (pm_info and pm_info[1].name in ("ADMIN", "WRITE"))
        or em_info
        or "platform-admin" in principal.roles
    )
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied to access this environment",
        )

    role_name = em_info[1].name if em_info else (pm_info[1].name if pm_info else "READ")

    return {
        "id": env.id,
        "project_id": env.project_id,
        "organization_id": env.tenant_id,
        "name": env.name,
        "slug": env.slug,
        "type": env.type,
        "description": env.description,
        "role": role_name,
        "created_at": env.created_at.isoformat(),
    }


@router.put("/environments/{environment_id}")
async def update_environment(
    environment_id: str,
    req: EnvironmentUpdateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    env = EnvironmentRepository().get_environment_by_id(db, environment_id)
    if not env:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")

    verify_tenant_scope(principal, env.tenant_id)

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, env.tenant_id, user.id)
        if user
        else None
    )
    pm_info = (
        MembershipRepository().get_project_membership(db, env.project_id, user.id) if user else None
    )
    em_info = (
        MembershipRepository().get_environment_membership(db, env.id, user.id) if user else None
    )

    can_update = bool(
        (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
        or (pm_info and pm_info[1].name == "ADMIN")
        or (em_info and em_info[1].name in ("ADMIN", "WRITE"))
        or "platform-admin" in principal.roles
        or "environment.update" in principal.permissions
    )
    if not can_update:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Cannot update environment",
        )

    updated = EnvironmentRepository().update_environment(
        db,
        environment_id=env.id,
        name=req.name,
        env_type=req.type,
        description=req.description,
    )

    AuditLogRepository().record_event(
        db,
        actor=user.id if user else principal.subject,
        actor_email=user.email if user else None,
        action="environment.updated",
        resource_type="environment",
        resource_id=env.id,
        organization_id=env.tenant_id,
        project_id=env.project_id,
        environment_id=env.id,
        details={"name": updated.name, "type": updated.type},
    )

    db.commit()

    return {
        "id": updated.id,
        "name": updated.name,
        "slug": updated.slug,
        "type": updated.type,
        "description": updated.description,
        "created_at": updated.created_at.isoformat(),
    }


@router.delete("/environments/{environment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_environment(
    environment_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    confirm_production_environment: Annotated[
        str | None,
        Header(alias="X-Confirm-Production-Environment"),
    ] = None,
):
    env = EnvironmentRepository().get_environment_by_id(db, environment_id)
    if not env:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")

    verify_tenant_scope(principal, env.tenant_id)

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, env.tenant_id, user.id)
        if user
        else None
    )
    pm_info = (
        MembershipRepository().get_project_membership(db, env.project_id, user.id) if user else None
    )

    can_delete = bool(
        (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
        or (pm_info and pm_info[1].name == "ADMIN")
        or "platform-admin" in principal.roles
    )
    if not can_delete:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Cannot delete environment",
        )
    if env.type == "Production" and confirm_production_environment != env.slug:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="Production deletion requires the X-Confirm-Production-Environment header to match the environment slug.",
        )

    AuditLogRepository().record_event(
        db,
        actor=user.id if user else principal.subject,
        actor_email=user.email if user else None,
        action="environment.deleted",
        resource_type="environment",
        resource_id=env.id,
        organization_id=env.tenant_id,
        project_id=env.project_id,
        environment_id=env.id,
        details={
            "slug": env.slug,
            "type": env.type,
            "production_confirmation": env.type == "Production",
        },
    )

    EnvironmentRepository().delete_environment(db, env.id)
    db.commit()


# ============================================================================
# Environment Members Sub-Routes
# ============================================================================


@router.get("/environments/{environment_id}/members")
async def list_environment_members(
    environment_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    env = EnvironmentRepository().get_environment_by_id(db, environment_id)
    if not env:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")

    verify_tenant_scope(principal, env.tenant_id)
    return MembershipRepository().list_environment_members(db, env.id)


@router.post("/environments/{environment_id}/members", status_code=status.HTTP_201_CREATED)
async def add_environment_member(
    environment_id: str,
    req: EnvironmentMemberRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    env = EnvironmentRepository().get_environment_by_id(db, environment_id)
    if not env:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")

    verify_tenant_scope(principal, env.tenant_id)

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, env.tenant_id, user.id)
        if user
        else None
    )
    pm_info = (
        MembershipRepository().get_project_membership(db, env.project_id, user.id) if user else None
    )

    can_manage = bool(
        (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
        or (pm_info and pm_info[1].name == "ADMIN")
        or "platform-admin" in principal.roles
    )
    if not can_manage:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Cannot manage environment members",
        )

    target_user = MembershipRepository().get_user_by_id(db, req.user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    em = MembershipRepository().add_environment_member(db, env.id, target_user.id, req.role)

    AuditLogRepository().record_event(
        db,
        actor=user.id if user else principal.subject,
        actor_email=user.email if user else None,
        action="environment.member_added",
        resource_type="environment_member",
        resource_id=target_user.id,
        organization_id=env.tenant_id,
        project_id=env.project_id,
        environment_id=env.id,
        details={"user_id": target_user.id, "role": req.role},
    )

    db.commit()

    return {
        "id": em.id,
        "environment_id": env.id,
        "user_id": target_user.id,
        "role": req.role,
        "created_at": em.created_at.isoformat(),
    }


@router.delete(
    "/environments/{environment_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_environment_member(
    environment_id: str,
    user_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    env = EnvironmentRepository().get_environment_by_id(db, environment_id)
    if not env:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")

    verify_tenant_scope(principal, env.tenant_id)

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, env.tenant_id, user.id)
        if user
        else None
    )
    pm_info = (
        MembershipRepository().get_project_membership(db, env.project_id, user.id) if user else None
    )

    can_manage = bool(
        (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
        or (pm_info and pm_info[1].name == "ADMIN")
        or "platform-admin" in principal.roles
    )
    if not can_manage:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Cannot manage environment members",
        )

    MembershipRepository().remove_environment_member(db, env.id, user_id)

    AuditLogRepository().record_event(
        db,
        actor=user.id if user else principal.subject,
        actor_email=user.email if user else None,
        action="environment.member_removed",
        resource_type="environment_member",
        resource_id=user_id,
        organization_id=env.tenant_id,
        project_id=env.project_id,
        environment_id=env.id,
        details={"user_id": user_id},
    )

    db.commit()
