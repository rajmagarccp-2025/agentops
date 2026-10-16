from fastapi.testclient import TestClient

from platform_api.main import app
from platform_api.security import issue_demo_token

client = TestClient(app)


def auth_header(*permissions: str, tenant_id: str = "remediation-tenant") -> dict[str, str]:
    token = issue_demo_token(tenant_id=tenant_id, permissions=permissions)
    return {"Authorization": f"Bearer {token}"}


def test_high_risk_remediation_requires_approval() -> None:
    response = client.post(
        "/api/v1/remediation/actions",
        headers=auth_header("remediation:execute"),
        json={
            "action": "kubernetes.scale_deployment",
            "parameters": {"namespace": "production", "deployment": "checkout-api", "replicas": 3},
            "idempotency_key": "scale-checkout-001",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approval_required"


def test_dry_run_is_verifiable_and_idempotent() -> None:
    body = {
        "action": "kubernetes.restart_pod",
        "parameters": {"namespace": "production", "pod_name": "checkout-api-1"},
        "dry_run": True,
        "idempotency_key": "restart-checkout-001",
    }
    first = client.post(
        "/api/v1/remediation/actions",
        headers=auth_header("remediation:execute"),
        json=body,
    )
    second = client.post(
        "/api/v1/remediation/actions",
        headers=auth_header("remediation:execute"),
        json=body,
    )
    assert first.status_code == 200
    assert second.json()["id"] == first.json()["id"]

    verified = client.post(
        f"/api/v1/remediation/actions/{first.json()['id']}/verify",
        headers=auth_header("remediation:verify"),
    )
    assert verified.status_code == 200
    assert verified.json()["verified"] is True


def test_rollback_is_critical_and_allowlisted() -> None:
    response = client.post(
        "/api/v1/remediation/actions",
        headers=auth_header("remediation:execute"),
        json={
            "action": "kubernetes.rollback_deployment",
            "parameters": {
                "namespace": "production",
                "deployment": "checkout-api",
                "revision": "v2.18.3",
            },
            "idempotency_key": "rollback-checkout-001",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approval_required"
