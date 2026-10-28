from fastapi.testclient import TestClient

from platform_api.llm.gateway import LLMGateway
from platform_api.llm.providers import MockProvider, ProviderCatalog
from platform_api.llm.service import llm_gateway
from platform_api.llm.telemetry import InMemoryLLMTelemetry
from platform_api.llm.types import (
    ChatMessage,
    LLMRequest,
    MessageRole,
    ProviderError,
    ProviderResponse,
)
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


def test_legacy_completion_requires_invoke_permission() -> None:
    response = client.post(
        "/api/v1/llmops/completions",
        headers=auth_header("llm:read"),
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 403


def test_legacy_completion_does_not_expose_provider_error(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise ProviderError("provider failed with api_key=synthetic-secret")

    monkeypatch.setattr(llm_gateway, "complete", fail)
    response = client.post(
        "/api/v1/llmops/completions",
        headers=auth_header("llm:invoke"),
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 503
    assert "synthetic-secret" not in response.text
    assert "x-llm-error" not in response.headers


def test_provider_health_is_authenticated() -> None:
    response = client.get("/api/v1/llmops/health-providers", headers=auth_header("llm:read"))
    assert response.status_code == 200
    assert response.json()["providers"] == {
        "mock-primary": "test-only",
        "mock-fallback": "test-only",
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


def test_gateway_rejects_missing_permission_before_quota_reservation() -> None:
    class RecordingQuota:
        reserved = False

        def reserve(self, tenant_id: str, tokens: int) -> None:
            self.reserved = True

        def settle(self, tenant_id: str, reserved_tokens: int, actual_tokens: int) -> None:
            return None

        def release(self, tenant_id: str, reserved_tokens: int) -> None:
            return None

    quota = RecordingQuota()
    gateway = LLMGateway(
        catalog=ProviderCatalog([MockProvider("primary", "model-primary")]),
        telemetry=InMemoryLLMTelemetry(),
        routes=[("primary", 1.0, 2.0)],
        quota=quota,
    )
    principal = Principal("user", "tenant", frozenset(), frozenset())

    try:
        gateway.complete(
            LLMRequest(messages=[ChatMessage(role=MessageRole.USER, content="hello")]),
            principal,
        )
    except ProviderError as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Gateway accepted a caller without llm:invoke")
    assert quota.reserved is False


def test_gateway_enforces_tenant_and_token_limits_before_provider_call() -> None:
    provider = MockProvider("primary", "model-primary")
    gateway = LLMGateway(
        catalog=ProviderCatalog([provider]),
        telemetry=InMemoryLLMTelemetry(),
        routes=[("primary", 1.0, 2.0)],
        max_input_tokens=4,
        max_output_tokens=2,
        max_total_tokens=6,
    )
    principal = Principal(
        "user", "tenant-a", frozenset(), frozenset({"llm:invoke"})
    )

    for request, status_code in (
        (
            LLMRequest(
                tenant_id="tenant-b",
                messages=[ChatMessage(role=MessageRole.USER, content="hi")],
            ),
            403,
        ),
        (
            LLMRequest(messages=[ChatMessage(role=MessageRole.USER, content="hello")]),
            413,
        ),
        (
            LLMRequest(
                max_output_tokens=4,
                token_budget=3,
                messages=[ChatMessage(role=MessageRole.USER, content="hi")],
            ),
            400,
        ),
    ):
        try:
            gateway.complete(request, principal)
        except ProviderError as exc:
            assert exc.status_code == status_code
        else:
            raise AssertionError(f"Gateway accepted an invalid request (expected {status_code})")
    assert provider.calls == 0


def test_gateway_cost_uses_configured_rate_and_approved_model() -> None:
    class FixedUsageProvider(MockProvider):
        def complete(self, request: LLMRequest) -> ProviderResponse:
            self.calls += 1
            return ProviderResponse(
                content="ok",
                model=request.model or self.model,
                input_tokens=1,
                output_tokens=2,
            )

    provider = FixedUsageProvider("primary", "model-primary")
    gateway = LLMGateway(
        catalog=ProviderCatalog([provider]),
        telemetry=InMemoryLLMTelemetry(),
        routes=[("primary", 1.0, 2.0)],
    )
    principal = Principal(
        "user", "tenant", frozenset(), frozenset({"llm:invoke"})
    )
    response = gateway.complete(
        LLMRequest(
            max_output_tokens=2,
            messages=[ChatMessage(role=MessageRole.USER, content="hello")],
        ),
        principal,
    )
    assert response.model == "mock-model"
    assert response.estimated_cost_usd == 0.000005


def test_gateway_does_not_retry_non_retryable_provider_error() -> None:
    class PermanentFailureProvider(MockProvider):
        def complete(self, request: LLMRequest) -> ProviderResponse:
            self.calls += 1
            raise ProviderError("safe provider error", retryable=False)

    primary = PermanentFailureProvider("primary", "model-primary")
    fallback = MockProvider("fallback", "model-fallback")
    gateway = LLMGateway(
        catalog=ProviderCatalog([primary, fallback]),
        telemetry=InMemoryLLMTelemetry(),
        routes=[("primary", 1.0, 2.0), ("fallback", 0.5, 1.0)],
        max_retries=3,
    )
    principal = Principal(
        "user", "tenant", frozenset(), frozenset({"llm:invoke"})
    )
    try:
        gateway.complete(
            LLMRequest(messages=[ChatMessage(role=MessageRole.USER, content="hello")]),
            principal,
        )
    except ProviderError:
        pass
    else:
        raise AssertionError("Gateway did not surface a permanent provider failure")
    assert primary.calls == 1
    assert fallback.calls == 0


def test_structured_output_failure_records_sanitized_usage_telemetry() -> None:
    class InvalidJsonProvider(MockProvider):
        def complete(self, request: LLMRequest) -> ProviderResponse:
            return ProviderResponse(
                content="not-json",
                model=request.model or self.model,
                input_tokens=1,
                output_tokens=2,
            )

    telemetry = InMemoryLLMTelemetry()
    gateway = LLMGateway(
        catalog=ProviderCatalog([InvalidJsonProvider("primary", "model-primary")]),
        telemetry=telemetry,
        routes=[("primary", 1.0, 2.0)],
    )
    principal = Principal(
        "user", "tenant", frozenset(), frozenset({"llm:invoke"})
    )
    request = LLMRequest(
        response_format="json",
        messages=[
            ChatMessage(role=MessageRole.USER, content="secret prompt not for telemetry")
        ],
    )
    try:
        gateway.complete(request, principal)
    except ProviderError:
        pass
    else:
        raise AssertionError("Gateway accepted malformed structured output")

    event = telemetry.events[0]
    assert event.input_tokens == 1
    assert event.output_tokens == 2
    assert event.error == "provider_error:503"
    assert "secret prompt" not in str(event)
