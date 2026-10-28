from datetime import UTC, datetime
from typing import Any

from platform_api.governance.repository import approval_repository
from platform_api.governance.schemas import (
    ApprovalRequest,
    ApprovalRequestCreate,
    ApprovalStatus,
)


def create_approval(
    tenant_id: str,
    requester: str,
    payload: ApprovalRequestCreate,
) -> ApprovalRequest:
    return approval_repository.create(tenant_id, requester, payload)


def decide_approval(
    tenant_id: str,
    request_id: str,
    approver: str,
    approved: bool,
    reason: str | None,
) -> ApprovalRequest:
    return approval_repository.decide(
        tenant_id,
        request_id,
        approver,
        ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED,
        reason,
    )


def consume_approval(tenant_id: str, request_id: str) -> ApprovalRequest:
    return approval_repository.consume(tenant_id, request_id)


def mark_approval_executed(tenant_id: str, request_id: str) -> ApprovalRequest:
    return approval_repository.mark_executed(tenant_id, request_id)


def reauthorize_execution(
    approval: ApprovalRequest,
    *,
    expected_tenant_id: str,
    expected_action: str,
    expected_resources: list[str],
    expected_parameters: dict[str, Any],
    expected_target_hash: str | None = None,
    current_evidence_count: int = 1,
) -> bool:

    # 1. Tenant Authorization & Exact Action Binding Check
    if approval.tenant_id != expected_tenant_id:
        raise ValueError(
            "Execution reauthorization DENIED: Tenant mismatch "
            f"({approval.tenant_id} != {expected_tenant_id})"
        )

    if approval.action != expected_action:
        raise ValueError(
            "Execution reauthorization DENIED: Action mismatch "
            f"({approval.action} != {expected_action})"
        )

    if approval.affected_resources != expected_resources:
        raise ValueError(
            "Execution reauthorization DENIED: Affected resources changed since approval"
        )

    if approval.parameters != expected_parameters:
        raise ValueError(
            "Execution reauthorization DENIED: Action parameters changed since approval"
        )

    if (
        expected_target_hash
        and approval.target_resource_hash
        and approval.target_resource_hash != expected_target_hash
    ):
        raise ValueError(
            "Execution reauthorization DENIED: Target resource state changed since approval"
        )

    # 2. Evidence Sufficiency Check
    if current_evidence_count < approval.required_evidence_count:
        raise ValueError(
            "Execution reauthorization DENIED: Insufficient evidence "
            f"({current_evidence_count} < {approval.required_evidence_count})"
        )

    # 3. Status, Expiry, and Replay Single-Use Checks
    if approval.status != ApprovalStatus.APPROVED:
        raise ValueError(
            "Execution reauthorization DENIED: Approval status is "
            f"{approval.status.value}, expected APPROVED"
        )

    if approval.consumed:
        raise ValueError(
            "Execution reauthorization DENIED: Approval replay detected (already executed)"
        )

    if approval.expires_at <= datetime.now(UTC):
        raise ValueError("Execution reauthorization DENIED: Approval has expired")

    return True
