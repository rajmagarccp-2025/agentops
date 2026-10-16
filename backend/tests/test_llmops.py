from fastapi.testclient import TestClient

from platform_api.main import app
from platform_api.security import issue_demo_token

client = TestClient(app)


def auth_header(*permissions: str, tenant_id: str = "llmops-tenant") -> dict[str, str]:
    token = issue_demo_token(tenant_id=tenant_id, permissions=permissions)
    return {"Authorization": f"Bearer {token}"}


def test_prompt_versions_are_tenant_scoped() -> None:
    created = client.post(
        "/api/v1/llmops/prompts",
        headers=auth_header("llm:write"),
        json={
            "name": "incident-investigator",
            "version": "3",
            "template": "Investigate using only cited evidence: {evidence}",
        },
    )
    assert created.status_code == 200

    prompts = client.get("/api/v1/llmops/prompts", headers=auth_header("llm:read"))
    assert prompts.status_code == 200
    assert prompts.json()[0]["version"] == "3"

    other = client.get(
        "/api/v1/llmops/prompts",
        headers=auth_header("llm:read", tenant_id="other-llmops-tenant"),
    )
    assert other.json() == []


def test_evaluation_computes_groundedness_and_correctness() -> None:
    response = client.post(
        "/api/v1/llmops/evaluations",
        headers=auth_header("llm:evaluate"),
        json={
            "dataset": "incident-regression-v1",
            "model": "mock-reasoner-v1",
            "input_text": "What caused the latency?",
            "output_text": "deployment latency evidence",
            "expected_text": "deployment latency evidence",
            "grounded": True,
            "tool_call_correct": True,
            "retrieval_quality": 0.9,
            "latency_ms": 120,
            "estimated_cost_usd": 0.0004,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["correctness"] == 1.0
    assert payload["groundedness"] == 1.0
    assert payload["success"] is True


def test_telemetry_is_tenant_scoped() -> None:
    completion = client.post(
        "/api/v1/llmops/completions",
        headers=auth_header("llm:invoke"),
        json={"messages": [{"role": "user", "content": "hello telemetry"}]},
    )
    assert completion.status_code == 200

    telemetry = client.get("/api/v1/llmops/telemetry", headers=auth_header("llm:read"))
    assert telemetry.status_code == 200
    assert telemetry.json()[-1]["request_id"] == completion.json()["request_id"]

    other = client.get(
        "/api/v1/llmops/telemetry",
        headers=auth_header("llm:read", tenant_id="other-llmops-tenant"),
    )
    assert other.json() == []
