from fastapi.testclient import TestClient

from platform_api.main import app
from platform_api.security import issue_demo_token

client = TestClient(app)


def test_metrics_endpoint_exposes_request_counters() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    metrics = client.get("/api/v1/metrics")
    assert metrics.status_code == 200
    assert "platform_http_requests_total" in metrics.text
    assert "platform_http_responses_200" in metrics.text


def test_workflow_and_tool_metrics_are_recorded() -> None:
    response = client.post(
        "/api/v1/agent-runs",
        headers={
            "Authorization": f"Bearer {issue_demo_token(permissions=('agents:run', 'tools:read'))}"
        },
        json={"request": "Discover resources", "request_type": "discovery"},
    )
    assert response.status_code == 202

    metrics = client.get("/api/v1/metrics")
    assert "platform_agent_runs_total" in metrics.text
    assert "platform_mcp_tool_executions" in metrics.text
