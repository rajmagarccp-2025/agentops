from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from platform_api.database import get_db
from platform_api.identity_repository import AuditLogRepository
from platform_api.secrets.schemas import (
    SecretAssignmentCreate,
    SecretAssignmentResponse,
    SecretCreate,
    SecretMetadataResponse,
    SecretProviderCreate,
    SecretProviderResponse,
    SecretResolveRequest,
    SecretResolveResponse,
    SecretUpdate,
    SecretValueRevealResponse,
)
from platform_api.secrets.service import SecretService
from platform_api.security import Principal, get_current_principal, require_permission

router = APIRouter(prefix="", tags=["secrets"])


# --- Secret Providers Endpoints ---
@router.get("/secret-providers", response_model=list[SecretProviderResponse])
async def list_secret_providers(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> list[SecretProviderResponse]:
    return SecretService(db).list_providers(principal)


@router.post(
    "/secret-providers", response_model=SecretProviderResponse, status_code=status.HTTP_201_CREATED
)
async def configure_secret_provider(
    req: SecretProviderCreate,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("secret_providers.configure"))],
) -> SecretProviderResponse:
    return SecretService(db).configure_provider(principal, req)


@router.post("/secret-providers/{provider_id}/test", response_model=dict[str, Any])
async def test_secret_provider_connection(
    provider_id: str,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("secret_providers.configure"))],
) -> dict[str, Any]:
    return SecretService(db).test_provider_connection(principal, provider_id)


# --- Secrets Endpoints ---
@router.get("/secrets", response_model=list[SecretMetadataResponse])
async def list_secrets(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("secrets.metadata.read"))],
    project_id: str | None = Query(None),
    environment_id: str | None = Query(None),
    scope: str | None = Query(None),
    secret_type: str | None = Query(None),
    search: str | None = Query(None),
) -> list[SecretMetadataResponse]:
    return SecretService(db).list_secrets(
        principal,
        project_id=project_id,
        environment_id=environment_id,
        scope=scope,
        secret_type=secret_type,
        search=search,
    )


@router.post("/secrets", response_model=SecretMetadataResponse, status_code=status.HTTP_201_CREATED)
async def create_secret(
    req: SecretCreate,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("secrets.create"))],
) -> SecretMetadataResponse:
    return SecretService(db).create_secret(principal, req)


@router.get("/secrets/{secret_id}", response_model=SecretMetadataResponse)
async def get_secret_metadata(
    secret_id: str,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("secrets.metadata.read"))],
) -> SecretMetadataResponse:
    return SecretService(db).get_secret_metadata(principal, secret_id)


@router.post("/secrets/{secret_id}/reveal", response_model=SecretValueRevealResponse)
async def reveal_secret_value(
    secret_id: str,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("secrets.value.read"))],
) -> SecretValueRevealResponse:
    return SecretService(db).reveal_secret_value(principal, secret_id)


@router.patch("/secrets/{secret_id}", response_model=SecretMetadataResponse)
async def update_secret(
    secret_id: str,
    req: SecretUpdate,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("secrets.update"))],
) -> SecretMetadataResponse:
    return SecretService(db).update_secret(principal, secret_id, req)


@router.post("/secrets/{secret_id}/rotate", response_model=SecretMetadataResponse)
async def rotate_secret(
    secret_id: str,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("secrets.rotate"))],
) -> SecretMetadataResponse:
    return SecretService(db).rotate_secret(principal, secret_id)


@router.post("/secrets/{secret_id}/revoke", response_model=dict[str, Any])
async def revoke_secret(
    secret_id: str,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("secrets.revoke"))],
) -> dict[str, Any]:
    return SecretService(db).revoke_secret(principal, secret_id)


@router.post(
    "/secrets/{secret_id}/assignments",
    response_model=SecretAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_entity_to_secret(
    secret_id: str,
    req: SecretAssignmentCreate,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("secrets.assign"))],
) -> SecretAssignmentResponse:
    return SecretService(db).assign_entity(principal, secret_id, req)


@router.delete("/secrets/{secret_id}/assignments/{assignment_id}", response_model=dict[str, Any])
async def revoke_entity_assignment(
    secret_id: str,
    assignment_id: str,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("secrets.unassign"))],
) -> dict[str, Any]:
    return SecretService(db).revoke_assignment(principal, secret_id, assignment_id)


@router.delete("/secrets/{secret_id}", response_model=dict[str, Any])
async def delete_secret(
    secret_id: str,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("secrets.delete"))],
) -> dict[str, Any]:
    return SecretService(db).delete_secret(principal, secret_id)


@router.post("/secrets/resolve", response_model=SecretResolveResponse)
async def resolve_runtime_secret(
    req: SecretResolveRequest,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> SecretResolveResponse:
    return SecretService(db).resolve_runtime_secret(principal, req)


@router.get("/secrets/{secret_id}/audit", response_model=list[dict[str, Any]])
async def list_secret_audit_events(
    secret_id: str,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("secrets.audit.read"))],
) -> list[dict[str, Any]]:
    logs = AuditLogRepository().list_events(
        db, tenant_id=principal.tenant_id, resource_id=secret_id, limit=100
    )
    return [
        {
            "id": log.id,
            "actor": log.actor,
            "actor_email": log.actor_email,
            "action": log.action,
            "resource_id": log.resource_id,
            "organization_id": log.organization_id,
            "project_id": log.project_id,
            "environment_id": log.environment_id,
            "details": log.details,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
