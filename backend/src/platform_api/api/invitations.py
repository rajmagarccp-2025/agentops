from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from platform_api.database import get_db
from platform_api.identity_repository import (
    AuditLogRepository,
    EnvironmentRepository,
    InvitationRepository,
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

router = APIRouter(prefix="/invitations", tags=["invitations"])


class CreateInvitationRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    organization_id: str = Field(..., min_length=1)
    role: str = Field("READ", pattern="^(ADMIN|WRITE|READ)$")
    project_id: str | None = None
    environment_id: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_invitation(
    req: CreateInvitationRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    tenant = TenantRepository().get_tenant_by_id(db, req.organization_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    verify_tenant_scope(principal, tenant.id)

    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, tenant.id, user.id) if user else None
    )
    caller_role = (
        mem_info[1].name if mem_info else ("ADMIN" if "platform-admin" in principal.roles else None)
    )

    if caller_role not in ("ADMIN", "OWNER") and "member.invite" not in principal.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Cannot create invitations",
        )

    # If project_id provided, verify it belongs to organization
    if req.project_id:
        proj = ProjectRepository().get_project_by_id(db, req.project_id)
        if not proj or proj.tenant_id != tenant.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project does not belong to organization",
            )

    # If environment_id provided, verify it belongs to project
    if req.environment_id:
        env = EnvironmentRepository().get_environment_by_id(db, req.environment_id)
        if (
            not env
            or env.tenant_id != tenant.id
            or (req.project_id and env.project_id != req.project_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Environment does not belong to project",
            )

    invitation = InvitationRepository().create_invitation(
        db,
        email=req.email,
        organization_id=tenant.id,
        role_name=req.role,
        created_by=user.id if user else principal.subject,
        project_id=req.project_id,
        environment_id=req.environment_id,
    )

    AuditLogRepository().record_event(
        db,
        actor=user.id if user else principal.subject,
        actor_email=user.email if user else None,
        action="invitation.created",
        resource_type="invitation",
        resource_id=invitation.id,
        organization_id=tenant.id,
        project_id=req.project_id,
        environment_id=req.environment_id,
        details={"invited_email": req.email, "role": req.role},
    )

    db.commit()

    return {
        "id": invitation.id,
        "email": invitation.email,
        "organization_id": invitation.organization_id,
        "project_id": invitation.project_id,
        "environment_id": invitation.environment_id,
        "role": req.role,
        "token": invitation.token,
        "invite_url": f"/invite/{invitation.token}",
        "expires_at": invitation.expires_at.isoformat(),
        "status": invitation.status,
    }


@router.get("/pending")
async def list_pending_invitations_for_current_user(
    principal: Annotated[Principal, Depends(get_optional_tenant_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    """Return pending invitations matching the authenticated user's email."""
    email = principal.email
    if not email:
        user = MembershipRepository().get_user_by_subject(db, principal.subject)
        email = user.email if user else None

    if not email:
        return []

    invitations = InvitationRepository().list_pending_for_email(db, email)
    result = []
    for inv in invitations:
        tenant = TenantRepository().get_tenant_by_id(db, inv.organization_id)
        proj = ProjectRepository().get_project_by_id(db, inv.project_id) if inv.project_id else None
        env = (
            EnvironmentRepository().get_environment_by_id(db, inv.environment_id)
            if inv.environment_id
            else None
        )
        result.append(
            {
                "id": inv.id,
                "organization_id": inv.organization_id,
                "organization_name": tenant.name if tenant else "Unknown Organization",
                "project_id": inv.project_id,
                "project_name": proj.name if proj else None,
                "environment_id": inv.environment_id,
                "environment_name": env.name if env else None,
                "token": inv.token,
                "status": inv.status,
                "expires_at": inv.expires_at.isoformat(),
            }
        )
    return result


@router.get("/org/{organization_id}")
async def list_org_invitations(
    organization_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    tenant = TenantRepository().get_tenant_by_id(db, organization_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    verify_tenant_scope(principal, tenant.id)
    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    mem_info = (
        MembershipRepository().get_organization_membership(db, tenant.id, user.id) if user else None
    )
    caller_role = (
        mem_info[1].name if mem_info else ("ADMIN" if "platform-admin" in principal.roles else None)
    )
    if caller_role not in ("ADMIN", "OWNER") and "member.invite" not in principal.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Cannot view invitations",
        )

    return InvitationRepository().list_organization_invitations(db, tenant.id)


@router.get("/{token}")
async def get_invitation_details(
    token: str,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Public endpoint: Allows checking invitation details prior to accepting."""
    inv = InvitationRepository().get_by_token(db, token)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    tenant = TenantRepository().get_tenant_by_id(db, inv.organization_id)
    proj = ProjectRepository().get_project_by_id(db, inv.project_id) if inv.project_id else None
    env = (
        EnvironmentRepository().get_environment_by_id(db, inv.environment_id)
        if inv.environment_id
        else None
    )

    from datetime import UTC, datetime

    exp = inv.expires_at if inv.expires_at.tzinfo else inv.expires_at.replace(tzinfo=UTC)
    is_expired = exp < datetime.now(UTC) or inv.status == "expired"

    return {
        "id": inv.id,
        "email": inv.email,
        "organization_id": inv.organization_id,
        "organization_name": tenant.name if tenant else "Unknown Organization",
        "project_id": inv.project_id,
        "project_name": proj.name if proj else None,
        "environment_id": inv.environment_id,
        "environment_name": env.name if env else None,
        "status": "expired" if is_expired else inv.status,
        "is_expired": is_expired,
        "is_accepted": inv.status == "accepted",
        "expires_at": inv.expires_at.isoformat(),
    }


@router.post("/{token}/accept")
async def accept_invitation(
    token: str,
    principal: Annotated[Principal, Depends(get_optional_tenant_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Accept an invitation explicitly after logging in or signing up."""
    inv = InvitationRepository().get_by_token(db, token)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    if inv.status == "accepted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has already been used."
        )

    from datetime import UTC, datetime

    exp = inv.expires_at if inv.expires_at.tzinfo else inv.expires_at.replace(tzinfo=UTC)
    if exp < datetime.now(UTC) or inv.status == "expired":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has expired."
        )

    existing_user = MembershipRepository().get_user_by_subject(db, principal.subject)
    authenticated_email = principal.email or (existing_user.email if existing_user else None)
    if (
        not authenticated_email
        or authenticated_email.strip().casefold() != inv.email.strip().casefold()
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This invitation is addressed to a different email account. "
                "Sign in with the invited account."
            ),
        )

    # Sync user in DB
    user = MembershipRepository().create_or_sync_user(
        db,
        subject=principal.subject,
        email=authenticated_email,
        display_name=principal.display_name or principal.subject,
    )

    invitation, msg = InvitationRepository().accept_invitation(db, token, user)
    if msg != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    AuditLogRepository().record_event(
        db,
        actor=user.id,
        actor_email=user.email,
        action="invitation.accepted",
        resource_type="invitation",
        resource_id=invitation.id,
        organization_id=invitation.organization_id,
        project_id=invitation.project_id,
        environment_id=invitation.environment_id,
        details={"accepted_by_user_id": user.id},
    )

    db.commit()

    tenant = TenantRepository().get_tenant_by_id(db, invitation.organization_id)

    return {
        "success": True,
        "message": "Invitation accepted successfully",
        "organization_id": invitation.organization_id,
        "organization_name": tenant.name if tenant else "Organization",
        "project_id": invitation.project_id,
        "environment_id": invitation.environment_id,
    }
