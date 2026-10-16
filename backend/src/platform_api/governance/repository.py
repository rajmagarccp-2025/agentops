from datetime import UTC, datetime

from sqlalchemy import select

from platform_api.config import get_settings
from platform_api.database import SessionLocal
from platform_api.governance.models import ApprovalRequestModel
from platform_api.governance.schemas import (
    ApprovalRequest,
    ApprovalRequestCreate,
    ApprovalStatus,
    expiration,
    new_id,
    now,
)
from platform_api.mcp.types import ToolRisk


class ApprovalRepository:
    def __init__(self) -> None:
        self._requests: dict[str, dict[str, ApprovalRequest]] = {}

    def create(
        self,
        tenant_id: str,
        requester: str,
        payload: ApprovalRequestCreate,
    ) -> ApprovalRequest:
        request = ApprovalRequest(
            **payload.model_dump(exclude={"expires_in_minutes"}),
            id=new_id(),
            tenant_id=tenant_id,
            requester=requester,
            created_at=now(),
            expires_at=expiration(payload.expires_in_minutes),
        )
        self._requests.setdefault(tenant_id, {})[request.id] = request
        return request

    def get(self, tenant_id: str, request_id: str) -> ApprovalRequest:
        try:
            return self._requests[tenant_id][request_id]
        except KeyError as exc:
            raise KeyError(request_id) from exc

    def list(self, tenant_id: str) -> list[ApprovalRequest]:
        return list(self._requests.get(tenant_id, {}).values())

    def decide(
        self,
        tenant_id: str,
        request_id: str,
        approver: str,
        status: ApprovalStatus,
        reason: str | None,
    ) -> ApprovalRequest:
        request = self.get(tenant_id, request_id)
        if request.status != ApprovalStatus.PENDING:
            raise ValueError("Approval request is no longer pending")
        if request.expires_at <= datetime.now(UTC):
            updated = request.model_copy(update={"status": ApprovalStatus.EXPIRED})
            self._requests[tenant_id][request_id] = updated
            raise ValueError("Approval request has expired")
        updated = request.model_copy(
            update={
                "status": status,
                "approver": approver,
                "decision_reason": reason,
                "decided_at": datetime.now(UTC),
            }
        )
        self._requests[tenant_id][request_id] = updated
        return updated

    def consume(
        self,
        tenant_id: str,
        request_id: str,
    ) -> ApprovalRequest:
        request = self.get(tenant_id, request_id)
        if request.status != ApprovalStatus.APPROVED:
            raise ValueError(
                f"Approval request status is {request.status.value}, expected APPROVED"
            )
        if request.consumed:
            raise ValueError("Approval request replay detected: already consumed")
        if request.expires_at <= datetime.now(UTC):
            raise ValueError("Approval request has expired")
        updated = request.model_copy(
            update={
                "consumed": True,
                "consumed_at": datetime.now(UTC),
            }
        )
        self._requests[tenant_id][request_id] = updated
        return updated


class SqlAlchemyApprovalRepository(ApprovalRepository):
    def create(
        self,
        tenant_id: str,
        requester: str,
        payload: ApprovalRequestCreate,
    ) -> ApprovalRequest:
        request = ApprovalRequest(
            **payload.model_dump(exclude={"expires_in_minutes"}),
            id=new_id(),
            tenant_id=tenant_id,
            requester=requester,
            created_at=now(),
            expires_at=expiration(payload.expires_in_minutes),
        )
        with SessionLocal() as session:
            session.add(ApprovalRequestModel(**request.model_dump()))
            session.commit()
        return request

    def get(self, tenant_id: str, request_id: str) -> ApprovalRequest:
        with SessionLocal() as session:
            model = session.scalar(
                select(ApprovalRequestModel).where(
                    ApprovalRequestModel.tenant_id == tenant_id,
                    ApprovalRequestModel.id == request_id,
                )
            )
            if model is None:
                raise KeyError(request_id)
            return _to_approval(model)

    def list(self, tenant_id: str) -> list[ApprovalRequest]:
        with SessionLocal() as session:
            models = session.scalars(
                select(ApprovalRequestModel)
                .where(ApprovalRequestModel.tenant_id == tenant_id)
                .order_by(ApprovalRequestModel.created_at.desc())
            ).all()
            return [_to_approval(model) for model in models]

    def decide(
        self,
        tenant_id: str,
        request_id: str,
        approver: str,
        status: ApprovalStatus,
        reason: str | None,
    ) -> ApprovalRequest:
        request = self.get(tenant_id, request_id)
        if request.status != ApprovalStatus.PENDING:
            raise ValueError("Approval request is no longer pending")
        if request.expires_at <= datetime.now(UTC):
            updated = request.model_copy(update={"status": ApprovalStatus.EXPIRED})
            return self._save_decision(updated)
        updated = request.model_copy(
            update={
                "status": status,
                "approver": approver,
                "decision_reason": reason,
                "decided_at": datetime.now(UTC),
            }
        )
        return self._save_decision(updated)

    def _save_decision(self, request: ApprovalRequest) -> ApprovalRequest:
        with SessionLocal() as session:
            model = session.get(ApprovalRequestModel, request.id)
            if model is None:
                raise KeyError(request.id)
            model.status = request.status.value
            model.approver = request.approver
            model.decision_reason = request.decision_reason
            model.decided_at = request.decided_at
            session.commit()
        return request


def _to_approval(model: ApprovalRequestModel) -> ApprovalRequest:
    return ApprovalRequest(
        id=model.id,
        tenant_id=model.tenant_id,
        requester=model.requester,
        action=model.action,
        tool_name=model.tool_name,
        reason=model.reason,
        risk=ToolRisk(model.risk),
        status=ApprovalStatus(model.status),
        affected_resources=model.affected_resources,
        parameters=model.parameters,
        run_id=model.run_id,
        approver=model.approver,
        decision_reason=model.decision_reason,
        created_at=model.created_at,
        expires_at=model.expires_at,
        decided_at=model.decided_at,
    )


approval_repository = (
    ApprovalRepository() if get_settings().demo_mode else SqlAlchemyApprovalRepository()
)
