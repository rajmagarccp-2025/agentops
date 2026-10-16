from fastapi.testclient import TestClient

from platform_api.main import app
from platform_api.observability import increment
from platform_api.security import issue_user_token

client = TestClient(app)


def auth_headers(*permissions: str) -> dict[str, str]:
    token = issue_user_token(
        subject="observability-viewer",
        email="observability-viewer@example.test",
        tenant_id="observability-test",
        permissions=permissions,
    )
    return {"Authorization": f"Bearer {token}"}


def test_metrics_snapshot_requires_permission_and_reports_process_scope() -> None:
    increment("http.requests.total", 3)
    permitted = client.get(
        "/api/v1/observability/metrics",
        headers=auth_headers("observability:read"),
    )
    assert permitted.status_code == 200
    data = permitted.json()
    assert data["scope"] == "process_and_database"
    assert data["metrics"]["http_requests_total"] >= 3

    denied = client.get(
        "/api/v1/observability/metrics",
        headers=auth_headers("rag:read"),
    )
    assert denied.status_code == 403
