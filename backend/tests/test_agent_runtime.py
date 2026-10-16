import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from platform_api.agents.service import agent_runtime
from platform_api.database import SessionLocal
from platform_api.main import app
from platform_api.security import issue_demo_token
from platform_api.workflow_job_runner import run_job
from platform_api.workflow_queue import WorkflowJobRecord, workflow_queue

client = TestClient(app)


def auth_header(*permissions: str) -> dict[str, str]:
    token = issue_demo_token(permissions=permissions)
    return {"Authorization": f"Bearer {token}"}


def execute_queued_run(run_id: str) -> dict[str, object]:
    with SessionLocal() as db:
        job = db.scalar(select(WorkflowJobRecord).where(WorkflowJobRecord.run_id == run_id))
        assert job is not None
        job_id = job.id
    assert workflow_queue.claim_by_id(job_id, worker_id="test-agent-runtime") is not None
    assert run_job(job_id) == 0
    response = client.get(
        f"/api/v1/agent-runs/{run_id}",
        headers=auth_header("agents:read"),
    )
    assert response.status_code == 200
    return response.json()


def test_discovery_run_routes_through_mcp_and_checkpoints_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = client.post(
        "/api/v1/agent-runs",
        headers=auth_header("agents:run", "tools:read"),
        json={"request": "Discover production resources", "request_type": "discovery"},
    )

    assert response.status_code == 202
    queued = response.json()
    assert queued["status"] == "pending"
    payload = execute_queued_run(queued["run_id"])
    assert payload["status"] == "completed"
    assert payload["evidence"][0]["resources"][0]["service"] == "checkout-api"
    assert payload["inventory_count"] == 2
    assert [step["agent"] for step in payload["steps"]] == ["supervisor", "discovery"]

    checkpoint_state = agent_runtime.get(payload["run_id"])
    monkeypatch.setattr(
        agent_runtime.graph,
        "invoke",
        lambda *_args, **_kwargs: pytest.fail("A completed checkpoint must not be replayed"),
    )
    recovered = agent_runtime.run(
        request=checkpoint_state["request"],
        request_type=checkpoint_state["request_type"],
        tenant_id=checkpoint_state["tenant_id"],
        subject=checkpoint_state["subject"],
        permissions=checkpoint_state["permissions"],
        run_id=payload["run_id"],
    )
    assert recovered["status"] == "completed"

    checkpoint = client.get(
        f"/api/v1/agent-runs/{payload['run_id']}",
        headers=auth_header("agents:read"),
    )
    assert checkpoint.status_code == 200
    assert checkpoint.json()["run_id"] == payload["run_id"]

    legacy_detail = client.get(
        f"/api/v1/agent-runs/{payload['run_id']}",
        headers=auth_header("agents:run"),
    )
    assert legacy_detail.status_code == 200

    recent = client.get("/api/v1/agent-runs", headers=auth_header("agents:read"))
    assert recent.status_code == 200
    assert any(item["run_id"] == payload["run_id"] for item in recent.json())

    other_tenant = issue_demo_token(tenant_id="other-tenant", permissions=("agents:read",))
    isolated = client.get(
        "/api/v1/agent-runs",
        headers={"Authorization": f"Bearer {other_tenant}"},
    )
    assert isolated.status_code == 200
    assert all(item["run_id"] != payload["run_id"] for item in isolated.json())

    inventory = client.get(
        "/api/v1/inventory/resources",
        headers=auth_header("inventory:read"),
    )
    assert inventory.status_code == 200
    assert len(inventory.json()) == 2


def test_inventory_is_tenant_scoped() -> None:
    token = issue_demo_token(
        tenant_id="other-tenant",
        permissions=("inventory:read",),
    )
    response = client.get(
        "/api/v1/inventory/resources",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_investigation_run_uses_llm_gateway() -> None:
    response = client.post(
        "/api/v1/agent-runs",
        headers=auth_header("agents:run", "llm:invoke"),
        json={"request": "Investigate elevated checkout latency", "request_type": "investigation"},
    )

    assert response.status_code == 202
    payload = execute_queued_run(response.json()["run_id"])
    assert payload["status"] == "completed"
    assert payload["findings"][0].startswith("Mock analysis for:")
    assert payload["steps"][-1]["agent"] == "investigation"


def test_remediation_run_pauses_for_approval() -> None:
    response = client.post(
        "/api/v1/agent-runs",
        headers=auth_header("agents:run", "tools:execute"),
        json={"request": "Scale checkout safely", "request_type": "remediation"},
    )

    assert response.status_code == 202
    payload = execute_queued_run(response.json()["run_id"])
    assert payload["status"] == "paused"
    assert payload["approval_required"] is True
    approval_id = payload["approval_id"]

    approval = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        headers=auth_header("approvals:approve"),
        json={"reason": "Incident commander approved the controlled scale operation."},
    )
    assert approval.status_code == 200
    assert approval.json()["status"] == "executed"

    resumed = client.get(
        f"/api/v1/agent-runs/{payload['run_id']}",
        headers=auth_header("agents:read"),
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "completed"


def test_agent_run_requires_permission() -> None:
    response = client.post(
        "/api/v1/agent-runs",
        headers=auth_header("tools:read"),
        json={"request": "Discover resources", "request_type": "discovery"},
    )

    assert response.status_code == 403


def test_specialist_agent_routes() -> None:
    routes = ["sre", "change", "finops", "security", "mlops", "llmops"]
    for route in routes:
        response = client.post(
            "/api/v1/agent-runs",
            headers=auth_header("agents:run", "tools:read", "llm:invoke"),
            json={
                "request": f"Execute {route} specialist workflow",
                "request_type": route,
                "cloud_provider": "aws",
                "environment": "production",
                "target_resource": "checkout-api",
            },
        )
        assert response.status_code == 202, f"Failed for route {route}: {response.text}"
        payload = execute_queued_run(response.json()["run_id"])
        assert payload["status"] == "completed"
        assert payload["request_type"] == route
        assert payload["cloud_provider"] == "aws"
        assert len(payload["findings"]) > 0
        assert payload["steps"][-1]["agent"] == route


def test_agent_run_streaming_endpoint() -> None:
    request_text = f"Stream discovery workflow {time.time_ns()}"
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            client.post,
            "/api/v1/agent-runs/stream",
            headers=auth_header("agents:run", "tools:read"),
            json={"request": request_text, "request_type": "discovery"},
        )
        job_id: str | None = None
        for _ in range(100):
            with SessionLocal() as db:
                jobs = db.scalars(
                    select(WorkflowJobRecord)
                    .where(WorkflowJobRecord.job_type == "agent_run")
                    .order_by(WorkflowJobRecord.created_at.desc())
                ).all()
                job = next(
                    (item for item in jobs if item.payload.get("request") == request_text),
                    None,
                )
                job_id = (
                    job.id
                    if job is not None and job.payload.get("request") == request_text
                    else None
                )
            if job_id:
                break
            time.sleep(0.05)
        assert job_id is not None
        assert workflow_queue.claim_by_id(job_id, worker_id="stream-test") is not None
        assert run_job(job_id) == 0
        response = future.result(timeout=15)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    text = response.text
    assert "data: " in text
    assert '"event": "start"' in text
    assert '"event": "complete"' in text
