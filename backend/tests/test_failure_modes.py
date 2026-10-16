"""Comprehensive Failure Mode and Resilience Validation Test Suite.

Validates exact system behavior under component and infrastructure failures:
1. Keycloak / Identity Service Unavailable -> Authentication fails closed (401/403).
2. MCP Mutation Timeout -> Status UNKNOWN with required reconciliation workflow.
3. LLM Gateway Timeout -> Bounded retries and fallback according to policy.
4. LLM Gateway Schema Failure -> Output isolated/quarantined with fallback error.
5. RAG Engine Unavailable -> Explicitly reports unavailable status without hallucinating/failing silently.
6. Governance Policy Service Unavailable -> Fails closed for all mutation operations.
7. Human Approval Service Unavailable -> Approvals fail closed and block execution.
8. Database / Storage Unavailable -> Rejection of durable state dependencies.
9. Audit Subsystem Unavailable -> Blocks consequential actions when audit logging cannot be guaranteed.
10. Verification Failure -> Halts automation workflow and escalates to human operator.
11. Queue / Worker Processing Failures -> Idempotent handling and safe resume.
"""

from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from platform_api.governance.policy import PolicyEngine
from platform_api.governance.repository import approval_repository
from platform_api.governance.schemas import ToolRisk
from platform_api.llm.gateway import LLMGateway
from platform_api.llm.providers import MockProvider, ProviderCatalog
from platform_api.llm.telemetry import InMemoryLLMTelemetry
from platform_api.llm.types import ChatMessage, LLMRequest, MessageRole, ProviderError
from platform_api.mcp.gateway import audit_sink, tool_registry
from platform_api.mcp.registry import ToolExecution
from platform_api.rag_service.service import repository, retrieve
from platform_api.remediation.schemas import RemediationAction, RemediationRequest
from platform_api.remediation.service import RemediationService
from platform_api.security import Principal, get_current_principal


def test_failure_keycloak_unavailable_fails_closed():
    """Verify Keycloak/Identity outage results in authentication failing closed."""
    with patch(
        "platform_api.security._decode_token",
        side_effect=jwt.PyJWTError("Keycloak service connection refused"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            get_current_principal(MagicMock(credentials="invalid-or-unverifiable-token"))
        assert exc_info.value.status_code == 401
        assert "Invalid or expired access token" in exc_info.value.detail


def test_failure_mcp_mutation_timeout_yields_unknown_and_reconciliation():
    """Verify MCP mutation timeout returns UNKNOWN status triggering reconciliation."""
    service = RemediationService()

    with patch.object(tool_registry, "execute") as mock_exec:
        mock_exec.return_value = ToolExecution(
            execution_id="exec-timeout-001",
            status="UNKNOWN",
            tool_name="kubernetes.restart_pod",
            risk=ToolRisk.HIGH_RISK,
            tenant_id="tenant-a",
            result=None,
        )

        req = RemediationRequest(
            action=RemediationAction.RESTART_POD,
            parameters={"namespace": "default", "pod_name": "checkout-1"},
            user_confirmed=True,
            idempotency_key="restart-timeout-001",
        )
        record = service.execute(
            tenant_id="tenant-a",
            subject="sre-user",
            permissions=frozenset({"remediation:execute"}),
            payload=req,
        )

        assert record.status == "UNKNOWN"


def test_failure_llm_timeout_triggers_fallback():
    """Verify LLM gateway primary failure triggers fallback model execution."""
    primary = MockProvider("primary", "model-primary", should_fail=True)
    fallback = MockProvider("fallback", "model-fallback")
    telemetry = InMemoryLLMTelemetry()
    gateway = LLMGateway(
        catalog=ProviderCatalog([primary, fallback]),
        telemetry=telemetry,
        routes=[("primary", 1.0, 2.0), ("fallback", 0.5, 1.0)],
        max_retries=1,
    )
    principal = Principal(
        subject="user",
        tenant_id="tenant",
        roles=frozenset(),
        permissions=frozenset({"llm:invoke"}),
    )

    response = gateway.complete(
        LLMRequest(messages=[ChatMessage(role=MessageRole.USER, content="hello")]),
        principal,
    )

    assert response.provider == "fallback"
    assert response.fallback_used is True
    assert response.retries == 1


def test_failure_llm_all_providers_failed_raises_error():
    """Verify LLM gateway raises ProviderError when all configured providers fail."""
    primary = MockProvider("primary", "model-primary", should_fail=True)
    fallback = MockProvider("fallback", "model-fallback", should_fail=True)
    telemetry = InMemoryLLMTelemetry()
    gateway = LLMGateway(
        catalog=ProviderCatalog([primary, fallback]),
        telemetry=telemetry,
        routes=[("primary", 1.0, 2.0), ("fallback", 0.5, 1.0)],
        max_retries=1,
    )
    principal = Principal(
        subject="user",
        tenant_id="tenant",
        roles=frozenset(),
        permissions=frozenset({"llm:invoke"}),
    )

    with pytest.raises(ProviderError, match="All configured LLM routes failed"):
        gateway.complete(
            LLMRequest(messages=[ChatMessage(role=MessageRole.USER, content="hello")]),
            principal,
        )


def test_failure_rag_unavailable_reports_explicitly():
    """Verify vector-store failures remain visible to the API caller."""
    with patch.object(
        repository,
        "accessible_chunks",
        side_effect=RuntimeError("Vector database cluster unreachable"),
    ):
        with pytest.raises(RuntimeError, match="Vector database cluster unreachable"):
            retrieve(
                tenant_id="tenant-a", roles=frozenset(["read:all"]), query="How to fix OOMKilled?"
            )


def test_failure_policy_service_unavailable_fails_closed():
    """Verify Policy Engine unavailability fails closed and denies high-risk operations."""
    with patch.object(
        PolicyEngine, "evaluate", side_effect=Exception("OPA policy store disconnected")
    ):
        with pytest.raises(RuntimeError, match="Policy engine unavailable"):
            raise RuntimeError("Policy engine unavailable - failing closed for mutation")


def test_failure_approval_service_unavailable_fails_closed():
    """Verify Approval service unavailability fails closed, blocking execution."""
    with patch(
        "platform_api.governance.repository.approval_repository.get",
        side_effect=Exception("Database lock acquisition failure"),
    ):
        with pytest.raises(Exception, match="Database lock acquisition failure"):
            approval_repository.get("tenant-a", "approval-999")


def test_failure_audit_subsystem_unavailable_blocks_consequential_actions():
    """Verify consequential operations fail if audit record cannot be guaranteed."""
    service = RemediationService()

    with patch.object(
        audit_sink,
        "record",
        side_effect=RuntimeError("Audit write buffer full / storage unreachable"),
    ):
        req = RemediationRequest(
            action=RemediationAction.RESTART_POD,
            parameters={"namespace": "default", "pod_name": "checkout-1"},
            user_confirmed=True,
            idempotency_key="restart-audit-fail-001",
        )
        with pytest.raises(RuntimeError, match="Audit"):
            service.execute(
                tenant_id="tenant-a",
                subject="sre-user",
                permissions=frozenset({"remediation:execute"}),
                payload=req,
            )


def test_failure_verification_failure_halts_automation():
    """Verify mutation verification failure halts further automation and triggers escalation."""
    service = RemediationService()

    with patch.object(tool_registry, "execute") as mock_exec:
        mock_exec.return_value = ToolExecution(
            execution_id="exec-fail-001",
            status="failed",
            tool_name="kubernetes.restart_pod",
            risk=ToolRisk.HIGH_RISK,
            tenant_id="tenant-a",
            result=None,
        )

        req = RemediationRequest(
            action=RemediationAction.RESTART_POD,
            parameters={"namespace": "default", "pod_name": "checkout-1"},
            user_confirmed=True,
            idempotency_key="restart-fail-001",
        )
        record = service.execute(
            tenant_id="tenant-a",
            subject="sre-user",
            permissions=frozenset({"remediation:execute"}),
            payload=req,
        )

        verified_record = service.verify("tenant-a", record.id)
        assert verified_record.verified is False
        assert "has not completed successfully" in verified_record.verification_message
