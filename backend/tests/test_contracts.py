"""Unit tests for platform contract schemas across all 20 specification categories."""

from datetime import UTC, datetime

from platform_api.contracts import (
    AgentInputScope,
    APIResponse,
    ApprovalRequest,
    ApprovalStatus,
    BlastRadius,
    ChatMessage,
    CloudProvider,
    ConsequentialAuditRecord,
    Environment,
    ErrorCode,
    ErrorDetail,
    EvidenceItem,
    EvidenceScope,
    EvidenceTimeWindow,
    FindingItem,
    LLMRequest,
    LLMResponse,
    MessageRole,
    ModelAlias,
    PageParams,
    PaginatedResponse,
    PolicyDecision,
    Principal,
    RecommendationItem,
    RemediationPlan,
    RemediationStatus,
    ResponseMetadata,
    RiskLevel,
    SharedAgentResultContract,
    SignalCheck,
    SimulationResult,
    StatementClassification,
    TenantContext,
    ToolRequest,
    ToolResponse,
    ToolRisk,
    ToolSpec,
    VerificationClass,
    VerificationResult,
    WorkflowStatus,
)


def test_domain_types() -> None:
    assert CloudProvider.AWS == "aws"
    assert Environment.PRODUCTION == "production"
    assert StatementClassification.OBSERVED == "observed"
    assert WorkflowStatus.AWAITING_APPROVAL == "awaiting_approval"


def test_api_response_envelope() -> None:
    meta = ResponseMetadata(request_id="req-123")
    resp = APIResponse[dict](success=True, data={"key": "val"}, meta=meta)
    assert resp.success is True
    assert resp.meta.request_id == "req-123"


def test_identity_and_tenant_schemas() -> None:
    principal = Principal(
        subject="usr-123",
        tenant_id="tenant-1",
        roles=frozenset({"admin"}),
        permissions=frozenset({"tools:execute"}),
    )
    assert principal.subject == "usr-123"

    tenant_ctx = TenantContext(
        tenant_id="tenant-1",
        environment=Environment.PRODUCTION,
        cloud_account_bindings={CloudProvider.AWS: "123456789012"},
    )
    assert tenant_ctx.cloud_account_bindings[CloudProvider.AWS] == "123456789012"


def test_evidence_finding_recommendation_schemas() -> None:
    scope = EvidenceScope(tenant_id="t1", service_id="checkout")
    window = EvidenceTimeWindow(start=datetime.now(UTC), end=datetime.now(UTC))
    evidence = EvidenceItem(
        evidence_id="ev-101",
        type="metric",
        source="cloudwatch",
        provider=CloudProvider.AWS,
        resource_id="res-1",
        scope=scope,
        window=window,
    )
    assert evidence.classification == StatementClassification.OBSERVED

    finding = FindingItem(
        finding_id="f-1",
        classification=StatementClassification.INFERRED,
        statement="Database latency spike correlated with deployment",
        evidence_refs=["ev-101"],
        confidence=0.92,
    )
    assert finding.confidence == 0.92

    rec = RecommendationItem(
        recommendation_id="r-1",
        rationale="High memory consumption",
        target_resource="k8s/deployment/checkout",
        expected_outcome="P95 latency below 200ms",
        proposed_action="scale",
        tool_name="k8s.scale_deployment",
        tool_parameters={"replicas": 5},
        risk_level=RiskLevel.MEDIUM_RISK,
        expires_at=datetime.now(UTC),
    )
    assert rec.risk_level == RiskLevel.MEDIUM_RISK


def test_shared_agent_result_contract() -> None:
    input_scope = AgentInputScope(tenant_id="t1", subject="u1")
    result = SharedAgentResultContract(
        run_id="run-1",
        tenant_id="t1",
        agent_id="sre-agent",
        status=WorkflowStatus.COMPLETED,
        input_scope=input_scope,
    )
    assert result.schema_version == "1.0"
    assert result.status == WorkflowStatus.COMPLETED


def test_mcp_tool_schemas() -> None:
    spec = ToolSpec(
        name="k8s.rollback",
        version="1.0",
        purpose="Rollback deployment",
        provider=CloudProvider.KUBERNETES,
        operation_type="mutation",
        risk_level=ToolRisk.HIGH_RISK,
    )
    assert spec.provider == CloudProvider.KUBERNETES

    req = ToolRequest(
        tool_name="k8s.rollback",
        parameters={"deployment": "checkout"},
        tenant_id="t1",
        request_id="r1",
        risk_level=ToolRisk.HIGH_RISK,
    )
    assert req.dry_run is False

    resp = ToolResponse(
        execution_id="exec-1",
        status="executed",
        tool_name="k8s.rollback",
        risk_level=ToolRisk.HIGH_RISK,
        tenant_id="t1",
    )
    assert resp.status == "executed"


def test_llm_gateway_schemas() -> None:
    msg = ChatMessage(role=MessageRole.USER, content="Investigate incident")
    req = LLMRequest(
        task="sre_triage",
        tenant_id="t1",
        model_alias=ModelAlias.REASONING_PRIMARY,
        messages=[msg],
    )
    assert req.model_alias == ModelAlias.REASONING_PRIMARY

    resp = LLMResponse(
        request_id="req-1",
        provider="mock",
        model="mock-v1",
        content="Incident RCA",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        estimated_cost_usd=0.002,
        latency_ms=120.5,
        retries=0,
    )
    assert resp.total_tokens == 150


def test_governance_remediation_simulation_verification_audit_schemas() -> None:
    policy = PolicyDecision(
        decision_id="p1",
        decision="approval_required",
        risk_level=RiskLevel.HIGH_RISK,
        reason="High risk mutation",
        rule_id="rule-99",
    )
    assert policy.decision == "approval_required"

    approval = ApprovalRequest(
        tenant_id="t1",
        requester_id="u1",
        run_id="run-1",
        tool_name="k8s.rollback",
        parameters_hash="hash-12345",
        risk_level=RiskLevel.HIGH_RISK,
    )
    assert approval.status == ApprovalStatus.PENDING

    plan = RemediationPlan(
        remediation_id="rem-1",
        recommendation_id="rec-1",
        tenant_id="t1",
        target_resource="checkout",
        allowlisted_tool="k8s.rollback",
    )
    assert plan.status == RemediationStatus.DRAFT

    sim = SimulationResult(
        simulation_id="sim-1",
        tool_name="k8s.rollback",
        target_resource="checkout",
        blast_radius=BlastRadius(impact_score=2.5),
        expected_outcome="Revert bad deployment",
        rollback_condition="Manual redeploy",
    )
    assert sim.blast_radius.impact_score == 2.5

    sig = SignalCheck(
        signal_name="latency",
        metric_or_health_check="P95",
        expected="<200ms",
        actual="120ms",
        passed=True,
    )
    verif = VerificationResult(
        verification_id="v1",
        remediation_id="rem-1",
        tenant_id="t1",
        status=VerificationClass.RECOVERED,
        signals_checked=[sig],
    )
    assert verif.status == VerificationClass.RECOVERED

    audit = ConsequentialAuditRecord(
        audit_id="a1",
        tenant_id="t1",
        principal_subject="u1",
        request_id="req1",
        run_id="run1",
        agent_id="remediation-agent",
        model_provider="openai",
        tool_name="k8s.rollback",
        tool_parameters_digest="digest1",
        policy_decision_id="p1",
        risk_level=RiskLevel.HIGH_RISK,
        executed_parameters_digest="digest1",
    )
    assert audit.audit_id == "a1"


def test_pagination_and_error_schemas() -> None:
    page_param = PageParams(page=1, limit=10)
    assert page_param.limit == 10

    res = PaginatedResponse[str](
        items=["item1"],
        total=1,
        page=1,
        limit=10,
        has_next=False,
        has_prev=False,
    )
    assert res.total == 1

    err = ErrorDetail(code=ErrorCode.AUTHORIZATION_ERROR, message="Access Denied")
    assert err.code == ErrorCode.AUTHORIZATION_ERROR
