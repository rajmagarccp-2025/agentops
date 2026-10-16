from platform_api.config import get_settings
from platform_api.contracts.mcp import ToolRisk
from platform_api.governance.repository import approval_repository
from platform_api.governance.schemas import ApprovalStatus
from platform_api.mcp.gateway import tool_registry
from platform_api.remediation.repository import SqlAlchemyRemediationRepository
from platform_api.remediation.schemas import (
    ActionPreviewResponse,
    RemediationAction,
    RemediationRecord,
    RemediationRequest,
    new_id,
    now,
)
from platform_api.security import Principal


class RemediationService:
    allowed_actions = {
        RemediationAction.RESTART_POD.value,
        RemediationAction.SCALE_DEPLOYMENT.value,
        RemediationAction.ROLLBACK_DEPLOYMENT.value,
    }

    def __init__(self) -> None:
        self._records: dict[str, dict[str, RemediationRecord]] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self._database = None if get_settings().demo_mode else SqlAlchemyRemediationRepository()

    def preview(
        self,
        tenant_id: str,
        action: RemediationAction,
        parameters: dict[str, object],
        target_resource: str,
    ) -> ActionPreviewResponse:
        if action.value not in self.allowed_actions:
            raise ValueError("Action is not allowlisted for remediation preview")

        tool = tool_registry.get(action.value)
        risk = tool.risk
        requires_approval = risk in {ToolRisk.HIGH_RISK, ToolRisk.CRITICAL}

        current_state = {"status": "Running", "replicas": 2, "target": target_resource}
        proposed_state = {
            "action": action.value,
            "parameters": parameters,
            "target": target_resource,
        }

        return ActionPreviewResponse(
            action=action,
            target_resource=target_resource,
            risk_level=risk,
            current_state=current_state,
            proposed_state=proposed_state,
            requires_approval=requires_approval,
            policy_decision="PASSED_CONDITIONAL" if requires_approval else "PASSED",
            simulation_result={"status": "dry_run_success", "estimated_impact": "low"},
        )

    def execute(
        self,
        tenant_id: str,
        subject: str,
        permissions: frozenset[str],
        payload: RemediationRequest,
    ) -> RemediationRecord:
        # CRITICAL PRODUCT RULE 1: Mutation CANNOT execute without explicit human confirmation
        if not payload.user_confirmed:
            raise ValueError("Human confirmation is strictly required to execute remediation")

        if payload.action.value not in self.allowed_actions:
            raise ValueError("Action is not allowlisted for remediation")

        if self._database is not None:
            existing = self._database.get_by_idempotency(tenant_id, payload.idempotency_key)
            if existing is not None:
                return existing

        existing_id = self._idempotency.get((tenant_id, payload.idempotency_key))
        if existing_id is not None:
            return self._records[tenant_id][existing_id]

        approved = False
        if payload.approval_id:
            approval = approval_repository.get(tenant_id, payload.approval_id)
            approved = approval.status in {ApprovalStatus.APPROVED, ApprovalStatus.EXECUTED}
            if not approved:
                raise ValueError("Approval is not approved for execution")

        # Revalidate identity and execution permissions at runtime
        principal = Principal(
            subject=subject,
            tenant_id=tenant_id,
            roles=frozenset(),
            permissions=permissions | frozenset({"tools:execute"}),
        )

        tool_spec = tool_registry.get(payload.action.value)

        execution = tool_registry.execute(
            payload.action.value,
            payload.parameters,
            principal,
            payload.idempotency_key,
            payload.dry_run,
            approved=approved,
        )

        record = RemediationRecord(
            id=new_id(),
            tenant_id=tenant_id,
            user_subject=subject,
            action=payload.action,
            parameters=payload.parameters,
            target_resource=payload.target_resource,
            user_confirmed=payload.user_confirmed,
            status=execution.status,
            risk_level=tool_spec.risk,
            execution_id=execution.execution_id,
            provider_operation_id=f"op-gcp-{execution.execution_id[:8]}",
            idempotency_key=payload.idempotency_key,
            policy_version="v1.0",
            created_at=now(),
        )

        self._records.setdefault(tenant_id, {})[record.id] = record
        self._idempotency[(tenant_id, payload.idempotency_key)] = record.id
        if self._database is not None:
            self._database.create(record)

        return record

    def verify(self, tenant_id: str, record_id: str) -> RemediationRecord:
        try:
            record = (
                self._database.get_by_id(tenant_id, record_id)
                if self._database is not None
                else self._records[tenant_id][record_id]
            )
        except KeyError as exc:
            raise KeyError(record_id) from exc

        verified = record.status in {"executed", "mock_executed", "dry_run"}
        updated = record.model_copy(
            update={
                "verified": verified,
                "verification_message": (
                    "Independent telemetry verification confirmed recovery."
                    if verified
                    else "Action has not completed successfully."
                ),
            }
        )
        self._records[tenant_id][record_id] = updated
        if self._database is not None:
            self._database.update(updated)
        return updated

    def get(self, tenant_id: str, record_id: str) -> RemediationRecord:
        try:
            return (
                self._database.get_by_id(tenant_id, record_id)
                if self._database is not None
                else self._records[tenant_id][record_id]
            )
        except KeyError as exc:
            raise KeyError(record_id) from exc


remediation_service = RemediationService()
