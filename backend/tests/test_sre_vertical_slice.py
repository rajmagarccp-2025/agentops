from platform_api.agents.runtime import agent_runtime
from platform_api.security import Principal


def test_sre_vertical_slice_end_to_end() -> None:
    # 1. User Authentication & Tenant Resolution
    principal = Principal(
        subject="sre-user-42",
        tenant_id="tenant-sre-prod",
        roles=frozenset(["sre", "user"]),
        permissions=frozenset({"agents:run", "tools:read", "rag:read", "llm:invoke"}),
    )

    # 2. Trigger AgentRun Investigation Flow
    request_text = "Check why my pod is down in my GKE cluster."
    state = agent_runtime.run(
        request=request_text,
        request_type="sre",
        tenant_id=principal.tenant_id,
        subject=principal.subject,
        permissions=list(principal.permissions),
        cloud_provider="gcp",
        environment="production",
        account_id="gcp-proj-sre-prod",
        region="us-central1",
        target_resource="checkout-api-pod-1",
        namespace="default",
        cluster="gke-prod-01",
        project_id="proj-sre-01",
        deployment="checkout-api",
    )

    # 3. State & Execution Validations
    assert state["run_id"] is not None
    assert state["status"] == "completed"
    assert state["tenant_id"] == "tenant-sre-prod"

    # 4. Telemetry Evidence Collection Verification (MCP GKE read-only tools)
    evidence_types = [ev.get("type") for ev in state["evidence"]]
    assert "gke.pod.get" in evidence_types
    assert "gke.pod.describe" in evidence_types
    assert "gke.pod.logs" in evidence_types
    assert "gke.pod.events" in evidence_types
    assert "gke.deployment.get" in evidence_types
    assert "gke.node.get" in evidence_types
    assert "gke.metrics.get" in evidence_types
    assert "change_event" in evidence_types

    # 5. Evidence-Backed Findings Categories Verification (OBSERVED / INFERRED / RECOMMENDED)
    structured_findings = state.get("structured_findings", [])
    assert len(structured_findings) > 0
    categories = {sf["category"] for sf in structured_findings}
    assert "OBSERVED" in categories
    assert "INFERRED" in categories
    assert "RECOMMENDED" in categories

    for sf in structured_findings:
        assert "evidence_ids" in sf
        assert len(sf["evidence_ids"]) > 0

    # 6. Hypotheses & Confidence
    hypotheses = state.get("hypotheses", [])
    assert len(hypotheses) > 0
    assert state.get("confidence", 0.0) > 0.0

    # 7. Missing Evidence & Recommendations
    assert len(state.get("missing_evidence", [])) > 0
    assert state.get("recommendation") is not None

    # 8. Mutation Safety Requirement: Ensure SRE Agent executed NO mutations
    for step in state["steps"]:
        assert step.get("action") != "mutation"
        assert "scale" not in step.get("agent", "")
        assert "restart" not in step.get("agent", "")
