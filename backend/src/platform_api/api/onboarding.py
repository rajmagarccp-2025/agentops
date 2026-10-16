from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from platform_api.database import get_db
from platform_api.identity_repository import (
    InvitationRepository,
    MembershipRepository,
    TenantRepository,
)
from platform_api.security import (
    Principal,
    get_optional_tenant_principal,
)

router = APIRouter(tags=["onboarding"])


@router.get("/onboarding/status")
async def get_onboarding_status(
    principal: Annotated[Principal, Depends(get_optional_tenant_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Check whether authenticated user has active organization memberships or pending invitations."""
    # Ensure user is synced
    user = MembershipRepository().create_or_sync_user(
        db,
        subject=principal.subject,
        email=principal.email or f"{principal.subject}@enterprise.com",
        display_name=principal.display_name or principal.subject,
    )
    db.commit()

    tenants = TenantRepository().list_user_tenants(db, user.id)
    pending_invites = InvitationRepository().list_pending_for_email(db, user.email)

    formatted_invites = []
    for inv in pending_invites:
        t = TenantRepository().get_tenant_by_id(db, inv.organization_id)
        formatted_invites.append(
            {
                "id": inv.id,
                "organization_id": inv.organization_id,
                "organization_name": t.name if t else "Organization",
                "token": inv.token,
                "role": "ADMIN" if inv.role_id == "ADMIN" else "READ",
                "expires_at": inv.expires_at.isoformat(),
            }
        )

    return {
        "user": {
            "id": user.id,
            "subject": user.subject,
            "email": user.email,
            "display_name": user.display_name,
        },
        "has_organization": len(tenants) > 0,
        "organizations_count": len(tenants),
        "organizations": [
            {
                "id": t.id,
                "name": t.name,
                "slug": t.slug,
                "description": t.description,
            }
            for t in tenants
        ],
        "pending_invitations": formatted_invites,
    }


@router.post("/auth/sync")
async def sync_user(
    principal: Annotated[Principal, Depends(get_optional_tenant_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Explicitly synchronize user identity from OIDC claims into the application database."""
    user = MembershipRepository().create_or_sync_user(
        db,
        subject=principal.subject,
        email=principal.email or f"{principal.subject}@enterprise.com",
        display_name=principal.display_name or principal.subject,
    )
    db.commit()
    return {
        "id": user.id,
        "subject": user.subject,
        "email": user.email,
        "display_name": user.display_name,
        "active": user.active,
    }
