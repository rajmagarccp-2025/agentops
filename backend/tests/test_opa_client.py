from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from platform_api.governance import opa
from platform_api.mcp.audit import InMemoryAuditSink
from platform_api.mcp.registry import (
    ToolPolicyUnavailableError,
    ToolRegistry,
    ToolSpec,
)
from platform_api.mcp.types import ToolCategory, ToolResult, ToolRisk
from platform_api.security import Principal


def _settings(*, endpoint: str | None = "http://opa:8181", required: bool = True):
    return SimpleNamespace(
        opa_url=endpoint,
        opa_required=required,
        opa_timeout_seconds=0.25,
        app_env="production" if required else "development",
    )


def test_opa_client_posts_to_decision_endpoint_and_parses_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def fake_post(url: str, *, json: dict[str, Any], timeout: float) -> httpx.Response:
        observed.update({"url": url, "json": json, "timeout": timeout})
        return httpx.Response(
            200,
            json={
                "result": {
                    "allowed": True,
                    "require_human_approval": False,
                    "policy_version": "v1.0.0",
                    "reason": "permitted",
                }
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(opa, "get_settings", lambda: _settings())
    monkeypatch.setattr(opa.httpx, "post", fake_post)
    result = opa.OPAPolicyClient().evaluate({"policy_version": "v1.0.0"})
    assert result is not None
    assert result.allowed
    assert observed == {
        "url": "http://opa:8181/v1/data/agentops/authz/decision",
        "json": {"input": {"policy_version": "v1.0.0"}},
        "timeout": 0.25,
    }


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectError("connection refused"),
        ValueError("invalid JSON"),
    ],
)
def test_opa_client_fails_closed_on_transport_or_response_error(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    def fail_post(*args: object, **kwargs: object) -> httpx.Response:
        raise failure

    monkeypatch.setattr(opa, "get_settings", lambda: _settings())
    monkeypatch.setattr(opa.httpx, "post", fail_post)
    with pytest.raises(opa.OPAUnavailable):
        opa.OPAPolicyClient().evaluate({"policy_version": "v1.0.0"})


def test_opa_client_rejects_stale_policy_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(opa, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        opa.httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(
            200,
            json={
                "result": {
                    "allowed": True,
                    "require_human_approval": False,
                    "policy_version": "v0.9.0",
                    "reason": "permitted",
                }
            },
            request=httpx.Request("POST", "http://opa:8181"),
        ),
    )
    with pytest.raises(opa.OPAUnavailable, match="stale"):
        opa.OPAPolicyClient().evaluate({"policy_version": "v1.0.0"})


def test_missing_required_opa_endpoint_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(opa, "get_settings", lambda: _settings(endpoint=None))
    with pytest.raises(opa.OPAUnavailable, match="not configured"):
        opa.OPAPolicyClient().evaluate({"policy_version": "v1.0.0"})


def test_opa_client_rejects_malformed_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(opa, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        opa.httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(
            200,
            json={"result": {"allowed": True}},
            request=httpx.Request("POST", "http://opa:8181"),
        ),
    )
    with pytest.raises(opa.OPAUnavailable, match="valid decision"):
        opa.OPAPolicyClient().evaluate({"policy_version": "v1.0.0"})


def test_mutating_tool_fails_closed_when_opa_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ScaleParameters(BaseModel):
        replicas: int

    handler_called = False

    def handler(parameters: ScaleParameters, tenant_id: str) -> ToolResult:
        nonlocal handler_called
        handler_called = True
        return ToolResult(status="executed", data={"replicas": parameters.replicas})

    registry = ToolRegistry(
        [
            ToolSpec(
                name="kubernetes.scale_deployment",
                description="Scale a deployment",
                category=ToolCategory.KUBERNETES,
                risk=ToolRisk.MEDIUM_RISK,
                required_permission="tools:execute",
                input_model=ScaleParameters,
                handler=handler,
            )
        ],
        InMemoryAuditSink(),
    )
    monkeypatch.setattr(
        "platform_api.mcp.registry.get_settings",
        lambda: SimpleNamespace(opa_required=False, app_env="production"),
    )
    monkeypatch.setattr(
        opa.opa_policy_client,
        "evaluate",
        lambda input_document: (_ for _ in ()).throw(opa.OPAUnavailable("offline")),
    )
    principal = Principal(
        subject="sre",
        tenant_id="tenant-a",
        roles=frozenset(),
        permissions=frozenset({"tools:execute"}),
    )
    with pytest.raises(ToolPolicyUnavailableError):
        registry.execute(
            "kubernetes.scale_deployment",
            {"replicas": 4},
            principal,
            "request-1",
            False,
        )
    assert not handler_called
