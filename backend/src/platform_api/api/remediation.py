from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from platform_api.remediation.schemas import (
    ActionPreviewResponse,
    RemediationAction,
    RemediationRecord,
    RemediationRequest,
)
from platform_api.remediation.service import remediation_service
from platform_api.security import Principal, require_permission

router = APIRouter(prefix="/remediation", tags=["remediation"])


class ActionPreviewRequest(BaseModel):
    action: RemediationAction
    parameters: dict[str, Any] = Field(default_factory=dict)
    target_resource: str = Field(min_length=1, max_length=200)


@router.post("/preview", response_model=ActionPreviewResponse)
async def preview_action(
    body: ActionPreviewRequest,
    principal: Annotated[Principal, Depends(require_permission("remediation:read"))],
) -> ActionPreviewResponse:
    try:
        return remediation_service.preview(
            principal.tenant_id,
            body.action,
            body.parameters,
            body.target_resource,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/actions", response_model=RemediationRecord)
async def execute_remediation(
    principal: Annotated[Principal, Depends(require_permission("remediation:execute"))],
    body: RemediationRequest,
) -> RemediationRecord:
    try:
        return remediation_service.execute(
            principal.tenant_id,
            principal.subject,
            principal.permissions,
            body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/actions/{record_id}/verify", response_model=RemediationRecord)
async def verify_remediation(
    record_id: str,
    principal: Annotated[Principal, Depends(require_permission("remediation:verify"))],
) -> RemediationRecord:
    try:
        return remediation_service.verify(principal.tenant_id, record_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remediation not found",
        ) from exc
