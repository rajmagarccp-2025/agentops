from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from platform_api.agents.service import agent_runtime
from platform_api.governance.repository import approval_repository
from platform_api.governance.schemas import ApprovalRequest, ApprovalStatus
from platform_api.governance.service import decide_approval
from platform_api.security import Principal, require_permission

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalDecision(BaseModel):
    reason: str | None = None


@router.get("", response_model=list[ApprovalRequest])
async def list_approvals(
    principal: Annotated[Principal, Depends(require_permission("approvals:read"))],
) -> list[ApprovalRequest]:
    return approval_repository.list(principal.tenant_id)


@router.get("/{request_id}", response_model=ApprovalRequest)
async def get_approval(
    request_id: str,
    principal: Annotated[Principal, Depends(require_permission("approvals:read"))],
) -> ApprovalRequest:
    try:
        return approval_repository.get(principal.tenant_id, request_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found",
        ) from exc


@router.post("/{request_id}/approve", response_model=ApprovalRequest)
async def approve(
    request_id: str,
    body: ApprovalDecision,
    principal: Annotated[Principal, Depends(require_permission("approvals:approve"))],
) -> ApprovalRequest:
    try:
        request = decide_approval(
            principal.tenant_id,
            request_id,
            principal.subject,
            True,
            body.reason,
        )
        if request.run_id:
            agent_runtime.resume_approved_remediation(request.run_id, principal.subject)
            request = request.model_copy(update={"status": ApprovalStatus.EXECUTED})
        return request
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{request_id}/reject", response_model=ApprovalRequest)
async def reject(
    request_id: str,
    body: ApprovalDecision,
    principal: Annotated[Principal, Depends(require_permission("approvals:approve"))],
) -> ApprovalRequest:
    try:
        return decide_approval(
            principal.tenant_id,
            request_id,
            principal.subject,
            False,
            body.reason,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
