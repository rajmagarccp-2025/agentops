from fastapi.testclient import TestClient

from platform_api.main import app
from platform_api.security import issue_demo_token

client = TestClient(app)


def auth_header(*permissions: str, tenant_id: str = "learning-tenant") -> dict[str, str]:
    token = issue_demo_token(tenant_id=tenant_id, permissions=permissions)
    return {"Authorization": f"Bearer {token}"}


def test_remediation_verification_compares_before_and_after_metrics() -> None:
    action = client.post(
        "/api/v1/remediation/actions",
        headers=auth_header("remediation:execute"),
        json={
            "action": "kubernetes.restart_pod",
            "parameters": {"namespace": "production", "pod_name": "checkout-api-2"},
            "dry_run": True,
            "idempotency_key": "learning-restart-001",
        },
    )
    assert action.status_code == 200
    record_id = action.json()["id"]

    verified = client.post(
        f"/api/v1/remediation/actions/{record_id}/verify",
        headers=auth_header("remediation:verify"),
    )
    assert verified.status_code == 200

    outcome = client.post(
        f"/api/v1/learning/remediation/{record_id}/verify",
        headers=auth_header("remediation:verify"),
    )
    assert outcome.status_code == 200
    payload = outcome.json()
    assert payload["recovered"] is True
    assert payload["metrics_before"]["error_rate_percent"] == 8.4
    assert payload["metrics_after"]["error_rate_percent"] == 1.2
    assert payload["deltas"]["latency_p95_ms"] == -620.0


def test_learning_feedback_is_tenant_scoped() -> None:
    action = client.post(
        "/api/v1/remediation/actions",
        headers=auth_header("remediation:execute", tenant_id="feedback-tenant"),
        json={
            "action": "kubernetes.restart_pod",
            "parameters": {"namespace": "production", "pod_name": "checkout-api-3"},
            "dry_run": True,
            "idempotency_key": "feedback-restart-001",
        },
    )
    record_id = action.json()["id"]
    feedback = client.post(
        "/api/v1/learning/feedback",
        headers=auth_header("learning:write", tenant_id="feedback-tenant"),
        json={"remediation_id": record_id, "useful": True, "notes": "Recovered quickly."},
    )
    assert feedback.status_code == 200

    other = client.get(
        "/api/v1/learning/feedback",
        headers=auth_header("learning:read", tenant_id="other-feedback-tenant"),
    )
    assert other.json() == []
