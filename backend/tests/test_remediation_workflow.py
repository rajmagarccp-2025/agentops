from platform_api.contracts.mcp import ToolRisk
from platform_api.remediation.schemas import RemediationAction, RemediationRequest
from platform_api.remediation.service import remediation_service


def test_ai_recommendation_cannot_execute_without_human_confirmation() -> None:
    tenant_id = "tenant-remediation-test"
    subject = "human-operator-1"
    permissions = frozenset({"remediation:execute", "tools:execute"})

    req_unconfirmed = RemediationRequest(
        action=RemediationAction.RESTART_POD,
        parameters={"namespace": "default", "pod_name": "checkout-api-pod-1"},
        target_resource="checkout-api-pod-1",
        user_confirmed=False,  # Unconfirmed recommendation
        idempotency_key="idemp-key-unconfirmed-101",
    )

    # Prove unconfirmed request raises error
    try:
        remediation_service.execute(tenant_id, subject, permissions, req_unconfirmed)
        assert False, "Should have failed execution because user_confirmed is False"
    except ValueError as exc:
        assert "Human confirmation is strictly required" in str(exc)


def test_human_confirmed_remediation_workflow_and_verification() -> None:
    tenant_id = "tenant-remediation-test"
    subject = "human-operator-1"
    permissions = frozenset({"remediation:execute", "tools:execute"})

    # 1. Action Preview
    preview = remediation_service.preview(
        tenant_id=tenant_id,
        action=RemediationAction.RESTART_POD,
        parameters={"namespace": "default", "pod_name": "checkout-api-pod-1"},
        target_resource="checkout-api-pod-1",
    )
    assert preview.action == RemediationAction.RESTART_POD
    assert preview.risk_level == ToolRisk.READ_ONLY or preview.risk_level == ToolRisk.MEDIUM_RISK
    assert preview.policy_decision is not None

    # 2. Confirmed Human Execution
    req_confirmed = RemediationRequest(
        action=RemediationAction.RESTART_POD,
        parameters={"namespace": "default", "pod_name": "checkout-api-pod-1"},
        target_resource="checkout-api-pod-1",
        user_confirmed=True,  # Explicitly confirmed by human operator
        idempotency_key="idemp-key-confirmed-202",
    )

    record = remediation_service.execute(tenant_id, subject, permissions, req_confirmed)
    assert record.id is not None
    assert record.tenant_id == tenant_id
    assert record.user_subject == subject
    assert record.user_confirmed is True
    assert record.provider_operation_id is not None

    # 3. Independent Recovery Verification
    verified_record = remediation_service.verify(tenant_id, record.id)
    assert verified_record.verified is True
    assert "Independent telemetry verification" in verified_record.verification_message
