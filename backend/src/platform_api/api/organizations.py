import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.database import get_db
from platform_api.identity_models import Tenant
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

router = APIRouter(prefix="/organizations", tags=["organizations"])


class OrganizationCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    slug: str | None = Field(None, max_length=100)
    description: str = Field("", max_length=500)
    logo_url: str | None = Field(None, max_length=500)


class OrganizationUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    description: str | None = Field(None, max_length=500)
    logo_url: str | None = Field(None, max_length=500)


class AddMemberRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    role: str = Field(..., pattern="^(ADMIN|WRITE|READ)$")


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(ADMIN|WRITE|READ)$")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", slug)


@router.get("")
async def list_organizations(
    principal: Annotated[Principal, Depends(get_optional_tenant_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    """List organizations the user belongs to."""
    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    if not user:
        # Fallback to token tenant memberships
        tenants = []
        for m in principal.tenant_memberships:
            t_id = m.get("tenant_id")
            if t_id:
                t = TenantRepository().get_tenant_by_id(
                    db, t_id
                ) or TenantRepository().get_tenant_by_slug(db, t_id)
                if t and t not in tenants:
                    tenants.append(t)
        if tenants:
            return [
                {
                    "id": t.id,
                    "name": t.name,
                    "slug": t.slug,
                    "description": t.description,
                    "created_at": t.created_at.isoformat(),
                }
                for t in tenants
            ]
        return []

    tenants = TenantRepository().list_user_tenants(db, user.id)
    result = []
    for t in tenants:
        mem, role = MembershipRepository().get_organization_membership(db, t.id, user.id) or (
            None,
            None,
        )
        result.append(
            {
                "id": t.id,
                "name": t.name,
                "slug": t.slug,
                "description": t.description,
                "logo_url": t.logo_url,
                "is_owner": mem.is_owner if mem else False,
                "role": role.name if role else "MEMBER",
                "created_at": t.created_at.isoformat(),
            }
        )
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_organization(
    req: OrganizationCreateRequest,
    principal: Annotated[Principal, Depends(get_optional_tenant_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Create a new organization. Creator automatically becomes Owner and ADMIN."""
    slug = req.slug or _slugify(req.name)
    existing = TenantRepository().get_tenant_by_slug(db, slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization with slug '{slug}' already exists",
        )

    # Sync user in database
    user = MembershipRepository().create_or_sync_user(
        db,
        subject=principal.subject,
        email=principal.email or f"{principal.subject}@enterprise.com",
        display_name=principal.display_name or principal.subject,
    )

    tenant = TenantRepository().create_tenant(
        db,
        name=req.name,
        slug=slug,
        description=req.description,
        created_by=user.id,
        logo_url=req.logo_url,
    )

    # Creator becomes ADMIN and is_owner = True
    MembershipRepository().add_organization_member(
        db,
        tenant_id=tenant.id,
        user_id=user.id,
        role_name="ADMIN",
        is_owner=True,
    )

    AuditLogRepository().record_event(
        db,
        actor=user.id,
        actor_email=user.email,
        action="organization.created",
        resource_type="organization",
        resource_id=tenant.id,
        organization_id=tenant.id,
        details={"name": tenant.name, "slug": tenant.slug},
    )

    db.commit()

    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "description": tenant.description,
        "logo_url": tenant.logo_url,
        "is_owner": True,
        "role": "ADMIN",
        "created_at": tenant.created_at.isoformat(),
    }


@router.get("/{organization_id}")
async def get_organization(
    organization_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    tenant = TenantRepository().get_tenant_by_id(db, organization_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    verify_tenant_scope(principal, tenant.id)

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, tenant.id, user.id) if user else None
    )
    mem, role = mem_info if mem_info else (None, None)

    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "description": tenant.description,
        "logo_url": tenant.logo_url,
        "is_owner": mem.is_owner if mem else False,
        "role": role.name if role else "MEMBER",
        "created_at": tenant.created_at.isoformat(),
    }


@router.put("/{organization_id}")
async def update_organization(
    organization_id: str,
    req: OrganizationUpdateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    tenant = TenantRepository().get_tenant_by_id(db, organization_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    verify_tenant_scope(principal, tenant.id)

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, tenant.id, user.id) if user else None
    )
    if not mem_info and "platform-admin" not in principal.roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    if (
        mem_info
        and mem_info[1].name not in ("ADMIN", "OWNER")
        and "platform-admin" not in principal.roles
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    updated = TenantRepository().update_tenant(
        db,
        tenant_id=tenant.id,
        name=req.name,
        description=req.description,
        logo_url=req.logo_url,
    )

    AuditLogRepository().record_event(
        db,
        actor=user.id if user else principal.subject,
        actor_email=user.email if user else None,
        action="organization.updated",
        resource_type="organization",
        resource_id=tenant.id,
        organization_id=tenant.id,
        details={"name": updated.name, "description": updated.description},
    )

    db.commit()

    return {
        "id": updated.id,
        "name": updated.name,
        "slug": updated.slug,
        "description": updated.description,
        "logo_url": updated.logo_url,
        "created_at": updated.created_at.isoformat(),
    }


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    organization_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    tenant = TenantRepository().get_tenant_by_id(db, organization_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    verify_tenant_scope(principal, tenant.id)

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, tenant.id, user.id) if user else None
    )
    is_owner = mem_info[0].is_owner if mem_info else False

    if not is_owner and "platform-admin" not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners can delete organizations",
        )

    AuditLogRepository().record_event(
        db,
        actor=user.id if user else principal.subject,
        actor_email=user.email if user else None,
        action="organization.deleted",
        resource_type="organization",
        resource_id=tenant.id,
        organization_id=tenant.id,
        details={"slug": tenant.slug},
    )

    TenantRepository().delete_tenant(db, tenant.id)
    db.commit()


# ============================================================================
# Organization Members Sub-Routes
# ============================================================================


@router.get("/{organization_id}/members")
async def list_members(
    organization_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    tenant = TenantRepository().get_tenant_by_id(db, organization_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    verify_tenant_scope(principal, tenant.id)
    return MembershipRepository().list_organization_members(db, tenant.id)


@router.post("/{organization_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    organization_id: str,
    req: AddMemberRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    tenant = TenantRepository().get_tenant_by_id(db, organization_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    verify_tenant_scope(principal, tenant.id)

    # Check caller has ADMIN or member.invite permission
    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, tenant.id, user.id) if user else None
    )
    caller_role = (
        mem_info[1].name if mem_info else ("ADMIN" if "platform-admin" in principal.roles else None)
    )

    if caller_role not in ("ADMIN", "OWNER") and "member.invite" not in principal.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied: Cannot invite members"
        )

    # Look up target user or create placeholder
    target_user = MembershipRepository().get_user_by_email(db, req.email)
    if not target_user:
        target_user = MembershipRepository().create_or_sync_user(
            db,
            subject=f"keycloak-{req.email}",
            email=req.email,
            display_name=req.email.split("@")[0].capitalize(),
        )

    mem = MembershipRepository().add_organization_member(
        db,
        tenant_id=tenant.id,
        user_id=target_user.id,
        role_name=req.role,
        is_owner=False,
    )

    AuditLogRepository().record_event(
        db,
        actor=user.id if user else principal.subject,
        actor_email=user.email if user else None,
        action="member.added",
        resource_type="organization_member",
        resource_id=target_user.id,
        organization_id=tenant.id,
        details={"email": target_user.email, "role": req.role},
    )

    db.commit()

    return {
        "membership_id": mem.id,
        "user_id": target_user.id,
        "email": target_user.email,
        "name": target_user.display_name,
        "role": req.role,
        "is_owner": mem.is_owner,
        "created_at": mem.created_at.isoformat(),
    }


@router.patch("/{organization_id}/members/{user_id}/role")
async def update_member_role(
    organization_id: str,
    user_id: str,
    req: UpdateMemberRoleRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    tenant = TenantRepository().get_tenant_by_id(db, organization_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    verify_tenant_scope(principal, tenant.id)

    caller = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, tenant.id, caller.id)
        if caller
        else None
    )
    caller_role = (
        mem_info[1].name if mem_info else ("ADMIN" if "platform-admin" in principal.roles else None)
    )

    if caller_role not in ("ADMIN", "OWNER") and "member.role_change" not in principal.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Cannot change member roles",
        )

    target_mem_info = MembershipRepository().get_organization_membership(db, tenant.id, user_id)
    if not target_mem_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in organization"
        )

    if target_mem_info[0].is_owner and req.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot downgrade organization owner role",
        )

    MembershipRepository().add_organization_member(
        db,
        tenant_id=tenant.id,
        user_id=user_id,
        role_name=req.role,
        is_owner=target_mem_info[0].is_owner,
    )

    AuditLogRepository().record_event(
        db,
        actor=caller.id if caller else principal.subject,
        actor_email=caller.email if caller else None,
        action="member.role_changed",
        resource_type="organization_member",
        resource_id=user_id,
        organization_id=tenant.id,
        details={"user_id": user_id, "new_role": req.role},
    )

    db.commit()

    return {"user_id": user_id, "role": req.role, "updated": True}


@router.delete("/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    organization_id: str,
    user_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    tenant = TenantRepository().get_tenant_by_id(db, organization_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    verify_tenant_scope(principal, tenant.id)

    caller = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, tenant.id, caller.id)
        if caller
        else None
    )
    caller_role = (
        mem_info[1].name if mem_info else ("ADMIN" if "platform-admin" in principal.roles else None)
    )

    if caller_role not in ("ADMIN", "OWNER") and "member.remove" not in principal.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied: Cannot remove members"
        )

    target_mem_info = MembershipRepository().get_organization_membership(db, tenant.id, user_id)
    if not target_mem_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in organization"
        )

    if target_mem_info[0].is_owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove organization owner"
        )

    MembershipRepository().remove_organization_member(db, tenant.id, user_id)

    AuditLogRepository().record_event(
        db,
        actor=caller.id if caller else principal.subject,
        actor_email=caller.email if caller else None,
        action="member.removed",
        resource_type="organization_member",
        resource_id=user_id,
        organization_id=tenant.id,
        details={"removed_user_id": user_id},
    )

    db.commit()


@router.get("/hierarchy")
async def get_user_hierarchy(
    principal: Annotated[Principal, Depends(get_optional_tenant_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    """Returns the multi-tenancy hierarchy for all organizations the user belongs to."""
    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    if not user and principal.email:
        user = MembershipRepository().get_user_by_email(db, principal.email)

    tenants = TenantRepository().list_user_tenants(db, user.id) if user else []
    if not tenants:
        # Fallback to all tenants if platform admin or demo
        if "platform-admin" in principal.roles or "ADMIN" in principal.roles:
            tenants = list(db.scalars(select(Tenant).where(Tenant.active.is_(True))).all())

    hierarchy = []
    for t in tenants:
        # 1. Members / Users
        members = MembershipRepository().list_organization_members(db, t.id)
        # 2. Projects & Environments
        projects = ProjectRepository().list_projects(db, t.id)
        proj_tree = []
        for p in projects:
            envs = EnvironmentRepository().list_environments(db, t.id, p.id)
            proj_tree.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "slug": p.slug,
                    "description": p.description,
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
                }
            )

        # 3. Active Autonomous Agents
        agents = [
            {
                "id": "agent-sre-01",
                "name": "AI SRE Incident Responder",
                "type": "SRE",
                "status": "active",
                "autonomy_level": "L3 (Supervised Execution)",
            },
            {
                "id": "agent-finops-01",
                "name": "FinOps Cloud Cost Optimizer",
                "type": "FinOps",
                "status": "active",
                "autonomy_level": "L4 (Autonomous Recommendations)",
            },
            {
                "id": "agent-llmops-01",
                "name": "LLMOps Gateway & Drift Detector",
                "type": "LLMOps",
                "status": "active",
                "autonomy_level": "L3 (Real-time Guardrails)",
            },
            {
                "id": "agent-security-01",
                "name": "Zero-Trust Security Auditor",
                "type": "Security",
                "status": "active",
                "autonomy_level": "L4 (Continuous Compliance)",
            },
        ]

        # 4. Standard Roles
        roles = [
            {
                "name": "ADMIN",
                "description": "Full enterprise organization, project & environment governance",
            },
            {
                "name": "WRITE",
                "description": "Read & Write operations, remediation approval, telemetry execution",
            },
            {"name": "READ", "description": "Read-only access across platform dashboards"},
        ]

        hierarchy.append(
            {
                "id": t.id,
                "name": t.name,
                "slug": t.slug,
                "description": t.description,
                "created_at": t.created_at.isoformat(),
                "users": members,
                "roles": roles,
                "projects": proj_tree,
                "agents": agents,
            }
        )

    return hierarchy


@router.get("/{organization_id}/hierarchy")
async def get_single_organization_hierarchy(
    organization_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Returns the full hierarchy for a specific organization."""
    tenant = TenantRepository().get_tenant_by_id(db, organization_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    verify_tenant_scope(principal, tenant.id)

    members = MembershipRepository().list_organization_members(db, tenant.id)
    projects = ProjectRepository().list_projects(db, tenant.id)
    proj_tree = []
    for p in projects:
        envs = EnvironmentRepository().list_environments(db, tenant.id, p.id)
        proj_tree.append(
            {
                "id": p.id,
                "name": p.name,
                "slug": p.slug,
                "description": p.description,
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
            }
        )

    agents = [
        {
            "id": "agent-sre-01",
            "name": "AI SRE Incident Responder",
            "type": "SRE",
            "status": "active",
            "autonomy_level": "L3",
        },
        {
            "id": "agent-finops-01",
            "name": "FinOps Cloud Cost Optimizer",
            "type": "FinOps",
            "status": "active",
            "autonomy_level": "L4",
        },
        {
            "id": "agent-llmops-01",
            "name": "LLMOps Gateway & Drift Detector",
            "type": "LLMOps",
            "status": "active",
            "autonomy_level": "L3",
        },
    ]

    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "description": tenant.description,
        "created_at": tenant.created_at.isoformat(),
        "users": members,
        "roles": [
            {"name": "ADMIN", "description": "Full administrative control"},
            {"name": "WRITE", "description": "Read & write access"},
            {"name": "READ", "description": "Read-only access"},
        ],
        "projects": proj_tree,
        "agents": agents,
    }
