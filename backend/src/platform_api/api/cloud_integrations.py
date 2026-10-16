from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from platform_api.contracts.domain import CloudProvider
from platform_api.database import get_db
from platform_api.environment_safety import require_active_environment
from platform_api.identity_repository import AuditLogRepository
from platform_api.integrations.models import CloudIntegrationModel
from platform_api.integrations.schemas import (
    CloudIntegrationCatalog,
    CloudIntegrationCreate,
    CloudIntegrationRecord,
    CloudProviderCapability,
)
from platform_api.security import Principal, require_permission

router = APIRouter(prefix="/cloud-integrations", tags=["cloud-integrations"])

_STATUS_DETAIL = (
    "Identity reference saved. Live provider verification is not configured; "
    "this record does not represent an authenticated cloud connection."
)


def _record(model: CloudIntegrationModel) -> CloudIntegrationRecord:
    return CloudIntegrationRecord(
        id=model.id,
        provider=CloudProvider(model.provider),
        display_name=model.display_name,
        account_id=model.account_id,
        identity_reference=model.identity_reference,
        status=model.status,
        status_detail=_STATUS_DETAIL,
        created_at=model.created_at,
    )


def _require_workspace(
    db: Session,
    principal: Principal,
    confirmation: str | None = None,
    *,
    destructive: bool = False,
) -> tuple[str, str]:
    require_active_environment(db, principal, confirmation, destructive=destructive)
    assert principal.project_id is not None
    assert principal.environment_id is not None
    return principal.project_id, principal.environment_id


@router.get("", response_model=CloudIntegrationCatalog)
async def list_cloud_integrations(
    principal: Annotated[Principal, Depends(require_permission("cloud:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> CloudIntegrationCatalog:
    project_id, environment_id = _require_workspace(db, principal)
    models = db.scalars(
        select(CloudIntegrationModel)
        .where(
            CloudIntegrationModel.tenant_id == principal.tenant_id,
            CloudIntegrationModel.project_id == project_id,
            CloudIntegrationModel.environment_id == environment_id,
        )
        .order_by(CloudIntegrationModel.created_at.desc())
    ).all()
    capabilities = [
        CloudProviderCapability(
            provider=provider,
            connection_mode="identity reference only",
            verification_supported=False,
        )
        for provider in CloudProvider
    ]
    return CloudIntegrationCatalog(
        providers=capabilities,
        connections=[_record(model) for model in models],
    )


@router.post("", response_model=CloudIntegrationRecord, status_code=status.HTTP_201_CREATED)
async def create_cloud_integration(
    body: CloudIntegrationCreate,
    principal: Annotated[Principal, Depends(require_permission("cloud:manage"))],
    db: Annotated[Session, Depends(get_db)],
) -> CloudIntegrationRecord:
    project_id, environment_id = _require_workspace(db, principal)
    model = CloudIntegrationModel(
        tenant_id=principal.tenant_id,
        project_id=project_id,
        environment_id=environment_id,
        provider=body.provider.value,
        display_name=body.display_name.strip(),
        account_id=body.account_id.strip(),
        identity_reference=body.identity_reference,
        status="unverified",
    )
    db.add(model)
    try:
        db.flush()
        AuditLogRepository().record_event(
            db,
            actor=principal.subject,
            actor_email=principal.email,
            action="cloud_integration.created",
            resource_type="cloud_integration",
            resource_id=model.id,
            organization_id=principal.tenant_id,
            project_id=project_id,
            environment_id=environment_id,
            details={
                "provider": body.provider.value,
                "account_id": model.account_id,
                "status": model.status,
            },
        )
        db.commit()
        db.refresh(model)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An integration for this provider and account already exists "
                "in this environment."
            ),
        ) from exc
    return _record(model)


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cloud_integration(
    integration_id: str,
    principal: Annotated[Principal, Depends(require_permission("cloud:manage"))],
    db: Annotated[Session, Depends(get_db)],
    confirm_production_environment: Annotated[
        str | None,
        Header(alias="X-Confirm-Production-Environment"),
    ] = None,
) -> None:
    project_id, environment_id = _require_workspace(
        db,
        principal,
        confirm_production_environment,
        destructive=True,
    )
    model = db.scalar(
        select(CloudIntegrationModel).where(
            CloudIntegrationModel.id == integration_id,
            CloudIntegrationModel.tenant_id == principal.tenant_id,
            CloudIntegrationModel.project_id == project_id,
            CloudIntegrationModel.environment_id == environment_id,
        )
    )
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cloud integration not found"
        )
    AuditLogRepository().record_event(
        db,
        actor=principal.subject,
        actor_email=principal.email,
        action="cloud_integration.deleted",
        resource_type="cloud_integration",
        resource_id=model.id,
        organization_id=principal.tenant_id,
        project_id=project_id,
        environment_id=environment_id,
        details={"provider": model.provider, "account_id": model.account_id},
    )
    db.delete(model)
    db.commit()
