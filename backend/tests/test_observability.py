import json
import logging
from uuid import uuid4

from fastapi.testclient import TestClient

from platform_api.logging_config import JsonFormatter
from platform_api.main import app
from platform_api.observability import metrics_snapshot, metrics_text
from platform_api.security import issue_demo_token

client = TestClient(app)


def test_metrics_endpoint_exposes_request_counters() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    metrics = client.get("/api/v1/metrics")
    assert metrics.status_code == 200
    assert "platform_http_requests_total" in metrics.text
    assert "platform_http_responses_200" in metrics.text


def test_http_metrics_use_bounded_route_and_actual_status() -> None:
    unique_path_segment = str(uuid4())
    response = client.get(f"/api/v1/not-a-route/{unique_path_segment}")
    assert response.status_code == 404

    metrics = metrics_text()
    assert "platform_http_responses_404" in metrics
    assert unique_path_segment not in metrics


def test_json_logs_redact_bearer_tokens() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request Authorization: Bearer abcdefghijklmnop",
        args=(),
        exc_info=None,
    )
    serialized = JsonFormatter().format(record)
    assert "abcdefghijklmnop" not in serialized
    assert "[REDACTED]" in json.loads(serialized)["message"]


def test_enqueue_records_queue_metric_not_execution_metrics() -> None:
    before = metrics_snapshot()
    response = client.post(
        "/api/v1/agent-runs",
        headers={
            "Authorization": (
                "Bearer "
                + issue_demo_token(
                    subject="test-user",
                    tenant_id="test-tenant",
                    permissions=("agents:run", "tools:read"),
                )
            )
        },
        json={"request": "Discover resources", "request_type": "discovery"},
    )
    assert response.status_code == 202

    after_enqueue = metrics_snapshot()
    assert (
        after_enqueue["workflow_jobs_enqueued_total"]
        == before["workflow_jobs_enqueued_total"] + 1
    )
    assert after_enqueue["workflow_executions_total"] == before["workflow_executions_total"]
    assert after_enqueue["tool_executions_total"] == before["tool_executions_total"]
