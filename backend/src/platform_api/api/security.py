from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.config import get_settings
from platform_api.database import get_db
from platform_api.identity_models import AuditLog
from platform_api.security import (
    Principal,
    get_optional_tenant_principal,
    require_permission,
)
from platform_api.security_investigation.schemas import (
    SecurityEvent,
    SecurityEventCreate,
    SecurityInvestigation,
)
from platform_api.security_investigation.service import ingest_event, investigate

router = APIRouter(prefix="/security", tags=["security"])


class SecurityOverviewResponse(BaseModel):
    auth_provider: str
    oidc_status: str
    oidc_realm: str
    oidc_client_id: str
    mfa_status: str
    tenant_isolation_mode: str
    active_user: dict[str, Any]
    roles: list[str]
    permissions_count: int
    session_id: str | None = None
    last_login: str
    security_events_count: int
    zero_trust_assertions: str
    recent_audit_events: list[dict[str, Any]]


@router.get("/overview", response_model=SecurityOverviewResponse)
@router.get("/status", response_model=SecurityOverviewResponse)
async def get_security_overview(
    principal: Annotated[Principal, Depends(get_optional_tenant_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> SecurityOverviewResponse:
    settings = get_settings()

    is_oidc = bool(principal.issuer and principal.issuer != settings.jwt_issuer)

    auth_provider = "OIDC identity provider" if is_oidc else "Platform-issued JWT"
    oidc_status = (
        "Session authenticated through OIDC" if is_oidc else "OIDC was not used for this session"
    )
    issuer = settings.oidc_issuer_url or principal.issuer or ""
    issuer_parts = [part for part in issuer.rstrip("/").split("/") if part]
    oidc_realm = (
        issuer_parts[issuer_parts.index("realms") + 1]
        if "realms" in issuer_parts and issuer_parts.index("realms") + 1 < len(issuer_parts)
        else "Not reported"
    )
    authentication_context = principal.authentication_context or {}
    authentication_methods = authentication_context.get("amr", [])
    mfa_reported = authentication_context.get("mfa") is True or (
        isinstance(authentication_methods, list)
        and any(
            "mfa" in str(method).lower() or "otp" in str(method).lower()
            for method in authentication_methods
        )
    )
    mfa_status = (
        "Reported by identity provider" if mfa_reported else "Not reported by identity provider"
    )

    # Fetch recent audit events for this tenant / user
    stmt = (
        select(AuditLog)
        .where(
            (AuditLog.actor == principal.subject)
            | (AuditLog.organization_id == principal.tenant_id)
        )
        .order_by(AuditLog.created_at.desc())
        .limit(10)
    )
    audit_records = list(db.scalars(stmt).all())
    recent_audit = [
        {
            "id": a.id,
            "action": a.action,
            "actor_email": a.actor_email or a.actor,
            "resource_type": a.resource_type,
            "created_at": a.created_at.isoformat(),
        }
        for a in audit_records
    ]

    return SecurityOverviewResponse(
        auth_provider=auth_provider,
        oidc_status=oidc_status,
        oidc_realm=oidc_realm,
        oidc_client_id=settings.oidc_client_id or "Not reported",
        mfa_status=mfa_status,
        tenant_isolation_mode="Organization scope from authenticated session",
        active_user={
            "subject_id": principal.subject_id or principal.subject,
            "email": principal.email or "Not reported",
            "display_name": principal.display_name or principal.subject,
            "tenant_id": principal.tenant_id or "Not reported",
        },
        roles=sorted(list(principal.roles)),
        permissions_count=len(principal.permissions),
        session_id=principal.session_id,
        last_login="Not tracked by this API",
        security_events_count=len(recent_audit),
        zero_trust_assertions="Tenant context reported by authenticated session",
        recent_audit_events=recent_audit,
    )


@router.post("/events", response_model=SecurityEvent)
async def ingest_security_event(
    body: SecurityEventCreate,
    principal: Annotated[Principal, Depends(require_permission("security:write"))],
) -> SecurityEvent:
    return ingest_event(principal.tenant_id, body)


@router.post("/investigations", response_model=SecurityInvestigation)
async def investigate_security(
    principal: Annotated[Principal, Depends(require_permission("security:investigate"))],
) -> SecurityInvestigation:
    return investigate(principal.tenant_id)
