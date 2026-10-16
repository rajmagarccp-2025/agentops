from datetime import UTC, datetime

from fastapi.testclient import TestClient

from platform_api.main import app
from platform_api.security import issue_demo_token

client = TestClient(app)


def auth_header(*permissions: str, tenant_id: str = "security-tenant") -> dict[str, str]:
    token = issue_demo_token(tenant_id=tenant_id, permissions=permissions)
    return {"Authorization": f"Bearer {token}"}


def test_security_investigation_collects_mcp_policy_violation() -> None:
    response = client.post(
        "/api/v1/security/investigations",
        headers=auth_header("security:investigate"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["event_count"] == 1
    assert payload["highest_severity"] == 4
    assert payload["findings"][0]["title"] == "Production role assumed from an untrusted network"
    assert payload["findings"][0]["requires_approval"] is True


def test_security_event_ingestion_is_tenant_scoped() -> None:
    response = client.post(
        "/api/v1/security/events",
        headers=auth_header("security:write", tenant_id="tenant-a"),
        json={
            "event_type": "iam",
            "title": "Excessive permissions granted",
            "actor": "operator",
            "occurred_at": datetime.now(UTC).isoformat(),
            "severity": 3,
            "source": "iam.mock",
            "details": {"permission": "admin"},
        },
    )
    assert response.status_code == 200

    other = client.post(
        "/api/v1/security/investigations",
        headers=auth_header("security:investigate", tenant_id="tenant-b"),
    )
    assert other.status_code == 200
    assert other.json()["event_count"] == 1


def test_security_routes_require_permissions() -> None:
    response = client.post(
        "/api/v1/security/investigations",
        headers=auth_header("finops:read"),
    )
    assert response.status_code == 403
