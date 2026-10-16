from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from platform_api.learning.schemas import (
    LearningFeedbackCreate,
    LearningRecord,
    VerificationResult,
)
from platform_api.learning.service import learning_service
from platform_api.remediation.service import remediation_service
from platform_api.security import Principal, require_permission

router = APIRouter(prefix="/learning", tags=["learning"])


@router.post("/remediation/{record_id}/verify", response_model=VerificationResult)
async def verify_remediation_outcome(
    record_id: str,
    principal: Annotated[Principal, Depends(require_permission("remediation:verify"))],
) -> VerificationResult:
    try:
        record = remediation_service.get(principal.tenant_id, record_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remediation not found",
        ) from exc
    return learning_service.verify(record)


@router.post("/feedback", response_model=LearningRecord)
async def add_feedback(
    body: LearningFeedbackCreate,
    principal: Annotated[Principal, Depends(require_permission("learning:write"))],
) -> LearningRecord:
    try:
        remediation_service.get(principal.tenant_id, body.remediation_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remediation not found",
        ) from exc
    return learning_service.add_feedback(principal.tenant_id, body)


@router.get("/verifications", response_model=list[VerificationResult])
async def list_verifications(
    principal: Annotated[Principal, Depends(require_permission("learning:read"))],
) -> list[VerificationResult]:
    return learning_service.list_verifications(principal.tenant_id)


@router.get("/feedback", response_model=list[LearningRecord])
async def list_feedback(
    principal: Annotated[Principal, Depends(require_permission("learning:read"))],
) -> list[LearningRecord]:
    return learning_service.list_feedback(principal.tenant_id)
