from datetime import UTC, date, datetime

from fastapi.testclient import TestClient

from platform_api.main import app
from platform_api.security import issue_demo_token

client = TestClient(app)
TENANT = "vertical-demo-tenant"


def auth_header(*permissions: str) -> dict[str, str]:
    token = issue_demo_token(
        tenant_id=TENANT,
        roles=("WRITE",),
        permissions=permissions,
        project_id="vertical-demo-project",
        environment_id="vertical-demo-production",
    )
    return {"Authorization": f"Bearer {token}"}


def test_demo_vertical_workflow() -> None:
    document = client.post(
        "/api/v1/rag/documents",
        headers=auth_header("rag:write"),
        json={
            "source": "demo/runbook.md",
            "title": "Checkout recovery runbook",
            "content": (
                "Check database pool saturation and verify recovery after an approved restart."
            ),
            "document_type": "runbook",
            "service": "checkout-api",
            "environment": "production",
        },
    )
    assert document.status_code == 200
    retrieval = client.post(
        "/api/v1/rag/retrieve",
        headers=auth_header("rag:read"),
        json={"query": "database pool recovery"},
    )
    assert retrieval.status_code == 200
    assert retrieval.json()["citations"]

    cost = client.post(
        "/api/v1/finops/costs",
        headers=auth_header("finops:write"),
        json={
            "period": str(date.today()),
            "provider": "demo-cloud",
            "account": "demo-account",
            "service": "checkout-api",
            "environment": "production",
            "amount_usd": 420,
        },
    )
    assert cost.status_code == 200
    utilization = client.post(
        "/api/v1/finops/utilization",
        headers=auth_header("finops:write"),
        json={
            "observed_on": str(date.today()),
            "resource_id": "vertical-checkout-001",
            "service": "checkout-api",
            "environment": "production",
            "cpu_percent": 18,
            "memory_percent": 32,
            "monthly_cost_usd": 420,
        },
    )
    assert utilization.status_code == 200

    incident = client.post(
        "/api/v1/incidents",
        headers=auth_header("incidents:write"),
        json={
            "title": "Checkout latency elevated",
            "service": "checkout-api",
            "severity": "P1",
            "started_at": datetime.now(UTC).isoformat(),
            "description": "Investigate the vertical demo incident.",
        },
    )
    assert incident.status_code == 200
    investigation = client.post(
        f"/api/v1/incidents/{incident.json()['id']}/investigate",
        headers=auth_header("incidents:investigate", "llm:invoke"),
    )
    assert investigation.status_code == 202
    assert investigation.json()["findings"]

    remediation = client.post(
        "/api/v1/remediation/actions",
        headers=auth_header("remediation:execute"),
        json={
            "action": "kubernetes.restart_pod",
            "parameters": {"namespace": "production", "pod_name": "checkout-api-demo"},
            "dry_run": True,
            "idempotency_key": "vertical-demo-restart",
        },
    )
    assert remediation.status_code == 200
    action_verified = client.post(
        f"/api/v1/remediation/actions/{remediation.json()['id']}/verify",
        headers=auth_header("remediation:verify"),
    )
    assert action_verified.status_code == 200
    assert action_verified.json()["verified"] is True
    verified = client.post(
        f"/api/v1/learning/remediation/{remediation.json()['id']}/verify",
        headers=auth_header("remediation:verify"),
    )
    assert verified.status_code == 200
    assert verified.json()["recovered"] is True
