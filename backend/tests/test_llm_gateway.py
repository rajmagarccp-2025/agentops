from fastapi.testclient import TestClient

from platform_api.llm.gateway import LLMGateway
from platform_api.llm.providers import MockProvider, ProviderCatalog
from platform_api.llm.telemetry import InMemoryLLMTelemetry
from platform_api.llm.types import ChatMessage, LLMRequest, MessageRole
from platform_api.main import app
from platform_api.security import Principal, issue_demo_token

client = TestClient(app)


def auth_header(*permissions: str) -> dict[str, str]:
    token = issue_demo_token(permissions=permissions)
    return {"Authorization": f"Bearer {token}"}


def test_completion_returns_usage_cost_and_structured_output() -> None:
    response = client.post(
        "/api/v1/llmops/completions",
        headers=auth_header("llm:invoke"),
        json={
            "task": "incident_summary",
            "response_format": "json",
            "messages": [{"role": "user", "content": "Summarize the supplied evidence."}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "mock-primary"
    assert payload["total_tokens"] == payload["input_tokens"] + payload["output_tokens"]
    assert payload["estimated_cost_usd"] >= 0
    assert payload["structured"]["grounded"] is True
    assert payload["fallback_used"] is False


def test_llm_routes_require_permission() -> None:
    response = client.get("/api/v1/llmops/models", headers=auth_header("tools:read"))
    assert response.status_code == 403


def test_provider_health_is_authenticated() -> None:
    response = client.get("/api/v1/llmops/health-providers", headers=auth_header("llm:read"))
    assert response.status_code == 200
    assert response.json()["providers"] == {
        "mock-primary": "configured",
        "mock-fallback": "configured",
    }


def test_gateway_falls_back_after_primary_failure() -> None:
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
    assert primary.calls == 2
    assert fallback.calls == 1
    assert len(telemetry.events) == 1
