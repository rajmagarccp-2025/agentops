from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from platform_api.main import app
from platform_api.security import issue_demo_token

client = TestClient(app)


def auth_header(*permissions: str, tenant_id: str = "demo-tenant") -> dict[str, str]:
    token = issue_demo_token(tenant_id=tenant_id, permissions=permissions)
    return {"Authorization": f"Bearer {token}"}


def test_incident_ingestion_and_evidence_based_investigation() -> None:
    started_at = datetime.now(UTC) - timedelta(minutes=12)
    response = client.post(
        "/api/v1/incidents",
        headers=auth_header("incidents:write"),
        json={
            "title": "Checkout latency elevated",
            "service": "checkout-api",
            "severity": "P1",
            "started_at": started_at.isoformat(),
            "description": "Investigate elevated latency after the latest deployment.",
        },
    )
    assert response.status_code == 200
    incident_id = response.json()["id"]

    investigation = client.post(
        f"/api/v1/incidents/{incident_id}/investigate",
        headers=auth_header("incidents:investigate", "llm:invoke"),
    )

    assert investigation.status_code == 202
    payload = investigation.json()
    assert payload["incident"]["confidence"] == 0.72
    assert len(payload["incident"]["timeline"]) >= 3
    assert payload["incident"]["evidence"][0]["data"]["error_rate_percent"] == 8.4
    assert payload["findings"][0].startswith("Mock analysis for:")


def test_incident_is_tenant_isolated() -> None:
    started_at = datetime.now(UTC).isoformat()
    response = client.post(
        "/api/v1/incidents",
        headers=auth_header("incidents:write", tenant_id="tenant-a"),
        json={
            "title": "Tenant A issue",
            "service": "orders",
            "severity": "P2",
            "started_at": started_at,
        },
    )
    incident_id = response.json()["id"]

    hidden = client.get(
        f"/api/v1/incidents/{incident_id}",
        headers=auth_header("incidents:read", tenant_id="tenant-b"),
    )
    assert hidden.status_code == 404


def test_incident_routes_require_permissions() -> None:
    response = client.post(
        "/api/v1/incidents",
        headers=auth_header("incidents:read"),
        json={
            "title": "Unauthorized issue",
            "service": "orders",
            "severity": "P3",
            "started_at": datetime.now(UTC).isoformat(),
        },
    )
    assert response.status_code == 403


def test_recorded_deployment_is_correlated_into_timeline() -> None:
    occurred_at = datetime.now(UTC) - timedelta(minutes=9)
    change = client.post(
        "/api/v1/changes",
        headers=auth_header("changes:write", tenant_id="change-tenant"),
        json={
            "service": "checkout-api",
            "environment": "production",
            "change_type": "deployment",
            "title": "checkout-api v2.19.0 deployed",
            "occurred_at": occurred_at.isoformat(),
            "source": "github-actions",
            "details": {"version": "v2.19.0"},
        },
    )
    assert change.status_code == 200

    incident = client.post(
        "/api/v1/incidents",
        headers=auth_header("incidents:write", tenant_id="change-tenant"),
        json={
            "title": "Checkout errors increased",
            "service": "checkout-api",
            "severity": "P1",
            "started_at": (occurred_at + timedelta(minutes=9)).isoformat(),
        },
    )
    incident_id = incident.json()["id"]
    investigation = client.post(
        f"/api/v1/incidents/{incident_id}/investigate",
        headers=auth_header("incidents:investigate", "llm:invoke", tenant_id="change-tenant"),
    )

    assert investigation.status_code == 202
    titles = [event["title"] for event in investigation.json()["incident"]["timeline"]]
    assert "checkout-api v2.19.0 deployed" in titles
