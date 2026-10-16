import pytest

from platform_api.contracts.domain import CloudProvider
from platform_api.mcp.gateway import tool_registry
from platform_api.mcp.registry import (
    ToolValidationError,
)
from platform_api.mcp.types import ToolRisk
from platform_api.security import Principal


def test_mcp_gke_read_only_tools() -> None:
    principal = Principal(
        "user-1", "tenant-mcp-test", frozenset(["user"]), frozenset(["tools:read"])
    )

    # Test gke.pod.get
    exec_pod = tool_registry.execute(
        name="gke.pod.get",
        parameters={
            "project_id": "proj-sre-01",
            "cluster": "gke-prod-01",
            "namespace": "default",
            "pod_name": "checkout-pod-1",
        },
        principal=principal,
        request_id="req-01",
        dry_run=False,
    )
    assert exec_pod.status == "executed"
    assert exec_pod.result is not None
    assert exec_pod.result.data["pod_name"] == "checkout-pod-1"
    assert exec_pod.result.data["provider"] == CloudProvider.GCP

    # Test gke.pod.logs
    exec_logs = tool_registry.execute(
        name="gke.pod.logs",
        parameters={
            "project_id": "proj-sre-01",
            "cluster": "gke-prod-01",
            "namespace": "default",
            "pod_name": "checkout-pod-1",
            "lines": 50,
        },
        principal=principal,
        request_id="req-02",
        dry_run=False,
    )
    assert exec_logs.status == "executed"
    assert "Application started" in exec_logs.result.data["logs"]


def test_mcp_gateway_isolation_and_credentials_prohibition() -> None:
    # Verify mock tools contain no credentials or raw access keys
    tool_spec = tool_registry.get("gke.pod.get")
    assert tool_spec.provider == CloudProvider.GCP
    assert tool_spec.risk == ToolRisk.READ_ONLY
    # Ensure no secrets in registry spec attributes
    assert not hasattr(tool_spec, "aws_secret_access_key")
    assert not hasattr(tool_spec, "service_account_key")


def test_mcp_sensitive_redaction() -> None:
    principal = Principal(
        "user-1", "tenant-mcp-test", frozenset(["user"]), frozenset(["tools:read"])
    )

    exec_res = tool_registry.execute(
        name="gke.pod.get",
        parameters={
            "project_id": "proj-sre-01",
            "cluster": "gke-prod-01",
            "namespace": "default",
            "pod_name": "checkout-pod-1",
            "secret_token": "bearer eyJhbGciOiJIUzI1NiJ9.secret",
        },
        principal=principal,
        request_id="req-03",
        dry_run=False,
    )
    assert exec_res.status == "executed"
    # Verify audit sink received redacted parameters
    last_event = tool_registry._audit_sink.events[-1]
    assert last_event.parameters["secret_token"] == "[REDACTED]"


def test_mcp_idempotency_and_version_validation() -> None:
    principal = Principal(
        "user-1", "tenant-mcp-test", frozenset(["user"]), frozenset(["tools:read"])
    )

    # Idempotent execution
    res1 = tool_registry.execute(
        name="gke.deployment.get",
        parameters={
            "project_id": "proj-sre-01",
            "cluster": "gke-prod-01",
            "namespace": "default",
            "deployment_name": "api",
        },
        principal=principal,
        request_id="req-idemp-1",
        dry_run=False,
        idempotency_key="idemp-key-999",
    )
    res2 = tool_registry.execute(
        name="gke.deployment.get",
        parameters={
            "project_id": "proj-sre-01",
            "cluster": "gke-prod-01",
            "namespace": "default",
            "deployment_name": "api",
        },
        principal=principal,
        request_id="req-idemp-2",
        dry_run=False,
        idempotency_key="idemp-key-999",
    )
    assert res1.execution_id == res2.execution_id

    other_tenant = Principal(
        "user-2", "tenant-mcp-other", frozenset(["user"]), frozenset(["tools:read"])
    )
    tenant_scoped = tool_registry.execute(
        name="gke.deployment.get",
        parameters={
            "project_id": "proj-sre-01",
            "cluster": "gke-prod-01",
            "namespace": "default",
            "deployment_name": "api",
        },
        principal=other_tenant,
        request_id="req-idemp-other-tenant",
        dry_run=False,
        idempotency_key="idemp-key-999",
    )
    assert tenant_scoped.tenant_id == "tenant-mcp-other"
    assert tenant_scoped.execution_id != res1.execution_id

    with pytest.raises(ToolValidationError, match="different tool request"):
        tool_registry.execute(
            name="gke.deployment.get",
            parameters={
                "project_id": "proj-sre-01",
                "cluster": "gke-prod-01",
                "namespace": "default",
                "deployment_name": "other-api",
            },
            principal=principal,
            request_id="req-idemp-mismatch",
            dry_run=False,
            idempotency_key="idemp-key-999",
        )

    # Provider mismatch failure
    with pytest.raises(ToolValidationError, match="Provider mismatch"):
        tool_registry.execute(
            name="gke.deployment.get",
            parameters={
                "project_id": "proj-sre-01",
                "cluster": "gke-prod-01",
                "namespace": "default",
                "deployment_name": "api",
            },
            principal=principal,
            request_id="req-err",
            dry_run=False,
            expected_provider=CloudProvider.AWS,
        )
