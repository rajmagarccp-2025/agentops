import re
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
    TenantRepository,
)
from platform_api.security import (
    Principal,
    get_current_principal,
    get_optional_tenant_principal,
    verify_tenant_scope,
)

router = APIRouter(tags=["projects"])


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    slug: str | None = Field(None, max_length=100)
    description: str = Field("", max_length=500)
    # Environment information is required with project creation
    initial_environment_name: str = Field("Development", min_length=2, max_length=100)
    initial_environment_type: str = Field(
        "Development", pattern="^(Development|QA|Staging|Production|UAT|Custom)$"
    )
    initial_environment_description: str = Field("", max_length=500)


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    description: str | None = Field(None, max_length=500)


class ProjectMemberRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    role: str = Field(..., pattern="^(ADMIN|WRITE|READ)$")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", slug)


@router.get("/organizations/{organization_id}/projects")
async def list_projects(
    organization_id: str,
    principal: Annotated[Principal, Depends(get_optional_tenant_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    tenant = TenantRepository().get_tenant_by_id(db, organization_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, tenant.id, user.id) if user else None
    )
    if not mem_info and principal.tenant_id and principal.tenant_id != tenant.id:
        verify_tenant_scope(principal, tenant.id)

    is_admin = bool(
        (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
        or "platform-admin" in principal.roles
        or "ADMIN" in principal.roles
    )

    projects = ProjectRepository().list_user_projects(
        db, tenant.id, user.id if user else "", is_org_admin=is_admin
    )
    result = []
    for p in projects:
        envs = EnvironmentRepository().list_environments(db, tenant.id, p.id)
        pm_info = MembershipRepository().get_project_membership(db, p.id, user.id) if user else None
        proj_role = pm_info[1].name if pm_info else (mem_info[1].name if mem_info else "READ")
        result.append(
            {
                "id": p.id,
                "organization_id": p.tenant_id,
                "name": p.name,
                "slug": p.slug,
                "description": p.description,
                "environments_count": len(envs),
                "role": proj_role,
                "created_at": p.created_at.isoformat(),
            }
        )
    return result


@router.post("/organizations/{organization_id}/projects", status_code=status.HTTP_201_CREATED)
async def create_project(
    organization_id: str,
    req: ProjectCreateRequest,
    principal: Annotated[Principal, Depends(get_optional_tenant_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    tenant = TenantRepository().get_tenant_by_id(db, organization_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You need an organization before creating a project.",
        )

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, tenant.id, user.id) if user else None
    )
    if not mem_info and principal.tenant_id and principal.tenant_id != tenant.id:
        verify_tenant_scope(principal, tenant.id)

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, tenant.id, user.id) if user else None
    )
    caller_role = (
        mem_info[1].name if mem_info else ("ADMIN" if "platform-admin" in principal.roles else None)
    )

    if caller_role not in ("ADMIN", "OWNER") and "project.create" not in principal.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Cannot create projects in this organization",
        )

    slug = req.slug or _slugify(req.name)
    existing = ProjectRepository().get_project_by_slug(db, tenant.id, slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with slug '{slug}' already exists in this organization",
        )

    project = ProjectRepository().create_project(
        db,
        tenant_id=tenant.id,
        name=req.name,
        slug=slug,
        description=req.description,
    )

    # Initial environment required with project
    env_slug = _slugify(req.initial_environment_name)
    env = EnvironmentRepository().create_environment(
        db,
        tenant_id=tenant.id,
        project_id=project.id,
        name=req.initial_environment_name,
        slug=env_slug,
        env_type=req.initial_environment_type,
        description=req.initial_environment_description,
    )

    # Add creator as project member and environment member
    if user:
        MembershipRepository().add_project_member(db, project.id, user.id, "ADMIN")
        MembershipRepository().add_environment_member(db, env.id, user.id, "ADMIN")

    AuditLogRepository().record_event(
        db,
        actor=user.id if user else principal.subject,
        actor_email=user.email if user else None,
        action="project.created",
        resource_type="project",
        resource_id=project.id,
        organization_id=tenant.id,
        project_id=project.id,
        details={"name": project.name, "initial_environment": env.name},
    )

    db.commit()

    return {
        "id": project.id,
        "organization_id": tenant.id,
        "name": project.name,
        "slug": project.slug,
        "description": project.description,
        "initial_environment": {
            "id": env.id,
            "name": env.name,
            "slug": env.slug,
            "type": env.type,
        },
        "created_at": project.created_at.isoformat(),
    }


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
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

    # Check project access
    has_access = bool(
        (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
        or pm_info
        or "platform-admin" in principal.roles
    )
    if not has_access:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    role_name = pm_info[1].name if pm_info else (mem_info[1].name if mem_info else "READ")
    envs = EnvironmentRepository().list_environments(db, project.tenant_id, project.id)

    return {
        "id": project.id,
        "organization_id": project.tenant_id,
        "name": project.name,
        "slug": project.slug,
        "description": project.description,
        "role": role_name,
        "environments": [
            {
                "id": e.id,
                "name": e.name,
                "slug": e.slug,
                "type": e.type,
                "description": e.description,
            }
            for e in envs
        ],
        "created_at": project.created_at.isoformat(),
    }


@router.get("/organizations/{organization_id}/projects/{project_id}")
async def get_org_project(
    organization_id: str,
    project_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    tenant = TenantRepository().get_tenant_by_id(db, organization_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    verify_tenant_scope(principal, tenant.id)

    project = ProjectRepository().get_project_by_id(db, project_id)
    if not project or project.tenant_id != tenant.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found in this organization"
        )

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, tenant.id, user.id) if user else None
    )
    pm_info = (
        MembershipRepository().get_project_membership(db, project.id, user.id) if user else None
    )

    has_access = bool(
        (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
        or pm_info
        or "platform-admin" in principal.roles
    )
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied to access this project"
        )

    role_name = pm_info[1].name if pm_info else (mem_info[1].name if mem_info else "READ")
    envs = EnvironmentRepository().list_environments(db, tenant.id, project.id)

    return {
        "id": project.id,
        "organization_id": project.tenant_id,
        "name": project.name,
        "slug": project.slug,
        "description": project.description,
        "role": role_name,
        "environments": [
            {
                "id": e.id,
                "name": e.name,
                "slug": e.slug,
                "type": e.type,
                "description": e.description,
            }
            for e in envs
        ],
        "created_at": project.created_at.isoformat(),
    }


@router.put("/projects/{project_id}")
async def update_project(
    project_id: str,
    req: ProjectUpdateRequest,
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

    can_update = bool(
        (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
        or (pm_info and pm_info[1].name in ("ADMIN", "WRITE"))
        or "platform-admin" in principal.roles
        or "project.update" in principal.permissions
    )
    if not can_update:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied: Cannot update project"
        )

    updated = ProjectRepository().update_project(
        db,
        project_id=project.id,
        name=req.name,
        description=req.description,
    )

    AuditLogRepository().record_event(
        db,
        actor=user.id if user else principal.subject,
        actor_email=user.email if user else None,
        action="project.updated",
        resource_type="project",
        resource_id=project.id,
        organization_id=project.tenant_id,
        project_id=project.id,
        details={"name": updated.name},
    )

    db.commit()

    return {
        "id": updated.id,
        "name": updated.name,
        "slug": updated.slug,
        "description": updated.description,
        "created_at": updated.created_at.isoformat(),
    }


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
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

    can_delete = bool(
        (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
        or (pm_info and pm_info[1].name == "ADMIN")
        or "platform-admin" in principal.roles
    )
    if not can_delete:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied: Cannot delete project"
        )

    AuditLogRepository().record_event(
        db,
        actor=user.id if user else principal.subject,
        actor_email=user.email if user else None,
        action="project.deleted",
        resource_type="project",
        resource_id=project.id,
        organization_id=project.tenant_id,
        project_id=project.id,
        details={"slug": project.slug},
    )

    ProjectRepository().delete_project(db, project.id)
    db.commit()


# ============================================================================
# Project Members Sub-Routes
# ============================================================================


@router.get("/projects/{project_id}/members")
async def list_project_members(
    project_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    project = ProjectRepository().get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    verify_tenant_scope(principal, project.tenant_id)
    return MembershipRepository().list_project_members(db, project.id)


@router.post("/projects/{project_id}/members", status_code=status.HTTP_201_CREATED)
async def add_project_member(
    project_id: str,
    req: ProjectMemberRequest,
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

    can_manage = bool(
        (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
        or (pm_info and pm_info[1].name == "ADMIN")
        or "platform-admin" in principal.roles
    )
    if not can_manage:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Cannot manage project members",
        )

    target_user = MembershipRepository().get_user_by_id(db, req.user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    pm = MembershipRepository().add_project_member(db, project.id, target_user.id, req.role)

    AuditLogRepository().record_event(
        db,
        actor=user.id if user else principal.subject,
        actor_email=user.email if user else None,
        action="project.member_added",
        resource_type="project_member",
        resource_id=target_user.id,
        organization_id=project.tenant_id,
        project_id=project.id,
        details={"user_id": target_user.id, "role": req.role},
    )

    db.commit()

    return {
        "id": pm.id,
        "project_id": project.id,
        "user_id": target_user.id,
        "role": req.role,
        "created_at": pm.created_at.isoformat(),
    }


@router.delete("/projects/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project_member(
    project_id: str,
    user_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
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

    can_manage = bool(
        (mem_info and mem_info[1].name in ("ADMIN", "OWNER"))
        or (pm_info and pm_info[1].name == "ADMIN")
        or "platform-admin" in principal.roles
    )
    if not can_manage:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Cannot manage project members",
        )

    MembershipRepository().remove_project_member(db, project.id, user_id)

    AuditLogRepository().record_event(
        db,
        actor=user.id if user else principal.subject,
        actor_email=user.email if user else None,
        action="project.member_removed",
        resource_type="project_member",
        resource_id=user_id,
        organization_id=project.tenant_id,
        project_id=project.id,
        details={"user_id": user_id},
    )

    db.commit()
