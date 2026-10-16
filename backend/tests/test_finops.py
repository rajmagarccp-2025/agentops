from datetime import date

from fastapi.testclient import TestClient

from platform_api.main import app
from platform_api.security import issue_demo_token

client = TestClient(app)


def auth_header(*permissions: str, tenant_id: str = "finops-tenant") -> dict[str, str]:
    token = issue_demo_token(tenant_id=tenant_id, permissions=permissions)
    return {"Authorization": f"Bearer {token}"}


def test_finops_ingestion_generates_rightsizing_and_idle_recommendations() -> None:
    response = client.post(
        "/api/v1/finops/costs",
        headers=auth_header("finops:write"),
        json={
            "period": str(date.today()),
            "provider": "aws",
            "account": "demo-account",
            "service": "payments-worker",
            "environment": "production",
            "amount_usd": 1000,
        },
    )
    assert response.status_code == 200

    utilization = client.post(
        "/api/v1/finops/utilization",
        headers=auth_header("finops:write"),
        json={
            "observed_on": str(date.today()),
            "resource_id": "worker-001",
            "service": "payments-worker",
            "environment": "production",
            "cpu_percent": 3,
            "memory_percent": 4,
            "monthly_cost_usd": 1000,
        },
    )
    assert utilization.status_code == 200

    summary = client.get("/api/v1/finops/summary", headers=auth_header("finops:read"))
    assert summary.status_code == 200
    payload = summary.json()
    types = {item["recommendation_type"] for item in payload["recommendations"]}
    assert "rightsizing" in types
    assert "idle_resource" in types
    assert payload["total_cost_usd"] == 1000
    assert all(item["requires_approval"] for item in payload["recommendations"])


def test_finops_detects_cost_anomaly() -> None:
    for amount in (100, 200):
        response = client.post(
            "/api/v1/finops/costs",
            headers=auth_header("finops:write", tenant_id="anomaly-tenant"),
            json={
                "period": str(date.today()),
                "provider": "aws",
                "account": "demo-account",
                "service": "search",
                "environment": "production",
                "amount_usd": amount,
            },
        )
        assert response.status_code == 200
    response = client.post(
        "/api/v1/finops/costs",
        headers=auth_header("finops:write", tenant_id="anomaly-tenant"),
        json={
            "period": str(date.today()),
            "provider": "aws",
            "account": "demo-account",
            "service": "search",
            "environment": "production",
            "amount_usd": 500,
        },
    )
    assert response.status_code == 200

    recommendations = client.get(
        "/api/v1/finops/recommendations",
        headers=auth_header("finops:read", tenant_id="anomaly-tenant"),
    )
    assert any(item["recommendation_type"] == "cost_anomaly" for item in recommendations.json())


def test_finops_is_tenant_scoped() -> None:
    response = client.get(
        "/api/v1/finops/summary",
        headers=auth_header("finops:read", tenant_id="other-finops-tenant"),
    )
    assert response.status_code == 200
    assert response.json()["total_cost_usd"] == 0
