from fastapi.testclient import TestClient

from platform_api.main import app
from platform_api.mcp.gateway import audit_sink
from platform_api.security import issue_demo_token

client = TestClient(app)


def auth_header(*permissions: str) -> dict[str, str]:
    token = issue_demo_token(permissions=permissions)
    return {"Authorization": f"Bearer {token}"}


def test_tool_discovery_is_authenticated_and_risk_aware() -> None:
    response = client.get("/api/v1/tools", headers=auth_header("tools:read"))

    assert response.status_code == 200
    tools = {tool["name"]: tool for tool in response.json()}
    assert tools["inventory.list_resources"]["risk"] == "READ_ONLY"
    assert tools["kubernetes.scale_deployment"]["risk"] == "HIGH_RISK"


def test_read_only_tool_executes_with_tenant_context() -> None:
    response = client.post(
        "/api/v1/tools/inventory.list_resources/execute",
        headers=auth_header("tools:read"),
        json={"parameters": {"environment": "production"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "executed"
    assert payload["tenant_id"] == "demo-tenant"
    assert payload["result"]["resources"][0]["service"] == "checkout-api"


def test_high_risk_tool_requires_approval_and_is_not_executed() -> None:
    before = len(audit_sink.events)
    response = client.post(
        "/api/v1/tools/kubernetes.scale_deployment/execute",
        headers=auth_header("tools:execute"),
        json={
            "parameters": {"namespace": "production", "deployment": "checkout-api", "replicas": 5}
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approval_required"
    assert response.json()["result"] is None
    assert len(audit_sink.events) == before + 1
    assert audit_sink.events[-1].outcome == "approval_required"


def test_tool_permission_is_enforced() -> None:
    response = client.post(
        "/api/v1/tools/kubernetes.restart_pod/execute",
        headers=auth_header("tools:read"),
        json={"parameters": {"namespace": "production", "pod_name": "checkout-api-1"}},
    )

    assert response.status_code == 403
    assert "tools:execute" in response.json()["detail"]


def test_tool_parameters_are_validated() -> None:
    response = client.post(
        "/api/v1/tools/kubernetes.restart_pod/execute",
        headers=auth_header("tools:execute"),
        json={"parameters": {"namespace": "production"}},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "validation_failed"
