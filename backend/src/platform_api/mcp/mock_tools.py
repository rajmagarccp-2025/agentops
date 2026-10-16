from typing import Annotated

from pydantic import BaseModel, Field

from platform_api.contracts.domain import CloudProvider
from platform_api.mcp.registry import ToolSpec
from platform_api.mcp.types import ToolCategory, ToolResult, ToolRisk

# --- GKE Read-Only Input Models ---


class PodGetQuery(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    cluster: str = Field(min_length=1, max_length=100)
    namespace: str = Field(default="default", min_length=1, max_length=100)
    pod_name: str = Field(min_length=1, max_length=200)


class PodDescribeQuery(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    cluster: str = Field(min_length=1, max_length=100)
    namespace: str = Field(default="default", min_length=1, max_length=100)
    pod_name: str = Field(min_length=1, max_length=200)


class PodLogsQuery(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    cluster: str = Field(min_length=1, max_length=100)
    namespace: str = Field(default="default", min_length=1, max_length=100)
    pod_name: str = Field(min_length=1, max_length=200)
    lines: int = Field(default=100, ge=1, le=2000)


class PodEventsQuery(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    cluster: str = Field(min_length=1, max_length=100)
    namespace: str = Field(default="default", min_length=1, max_length=100)
    pod_name: str = Field(min_length=1, max_length=200)


class DeploymentGetQuery(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    cluster: str = Field(min_length=1, max_length=100)
    namespace: str = Field(default="default", min_length=1, max_length=100)
    deployment_name: str = Field(min_length=1, max_length=200)


class NodeGetQuery(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    cluster: str = Field(min_length=1, max_length=100)
    node_name: str = Field(min_length=1, max_length=200)


class MetricsGetQuery(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    cluster: str = Field(min_length=1, max_length=100)
    resource_kind: str = Field(min_length=1, max_length=50)
    resource_name: str = Field(min_length=1, max_length=200)


# --- Legacy / Standard Query Models ---


class InventoryQuery(BaseModel):
    environment: str = Field(default="production", min_length=1, max_length=100)


class PodQuery(BaseModel):
    namespace: str = Field(default="default", min_length=1, max_length=100)


class RestartPodRequest(BaseModel):
    namespace: str = Field(min_length=1, max_length=100)
    pod_name: str = Field(min_length=1, max_length=200)


class ScaleDeploymentRequest(BaseModel):
    namespace: str = Field(min_length=1, max_length=100)
    deployment: str = Field(min_length=1, max_length=200)
    replicas: Annotated[int, Field(ge=0, le=100)]


class RollbackDeploymentRequest(BaseModel):
    namespace: str = Field(min_length=1, max_length=100)
    deployment: str = Field(min_length=1, max_length=200)
    revision: str = Field(min_length=1, max_length=100)


class IncidentSignalsQuery(BaseModel):
    service: str = Field(min_length=1, max_length=200)


class SecurityEventsQuery(BaseModel):
    environment: str = Field(default="production", min_length=1, max_length=100)


# --- GKE Handlers ---


def gke_pod_get(query: PodGetQuery, tenant_id: str) -> ToolResult:
    return ToolResult(
        status="ok",
        data={
            "tenant_id": tenant_id,
            "provider": CloudProvider.GCP,
            "project_id": query.project_id,
            "cluster": query.cluster,
            "namespace": query.namespace,
            "pod_name": query.pod_name,
            "phase": "Running",
            "ip": "10.4.12.89",
            "containers": ["app", "sidecar"],
        },
    )


def gke_pod_describe(query: PodDescribeQuery, tenant_id: str) -> ToolResult:
    return ToolResult(
        status="ok",
        data={
            "tenant_id": tenant_id,
            "provider": CloudProvider.GCP,
            "project_id": query.project_id,
            "cluster": query.cluster,
            "namespace": query.namespace,
            "pod_name": query.pod_name,
            "node_name": "gke-prod-pool-1-abc12345",
            "status": "Running",
            "qos_class": "Guaranteed",
            "restart_count": 0,
        },
    )


def gke_pod_logs(query: PodLogsQuery, tenant_id: str) -> ToolResult:
    return ToolResult(
        status="ok",
        data={
            "tenant_id": tenant_id,
            "provider": CloudProvider.GCP,
            "project_id": query.project_id,
            "cluster": query.cluster,
            "namespace": query.namespace,
            "pod_name": query.pod_name,
            "lines_returned": query.lines,
            "logs": (
                f"2026-09-29T10:00:00Z [INFO] Application started on pod {query.pod_name}\n"
                "2026-09-29T10:01:00Z [INFO] Health check passed."
            ),
        },
    )


def gke_pod_events(query: PodEventsQuery, tenant_id: str) -> ToolResult:
    return ToolResult(
        status="ok",
        data={
            "tenant_id": tenant_id,
            "provider": CloudProvider.GCP,
            "project_id": query.project_id,
            "cluster": query.cluster,
            "namespace": query.namespace,
            "pod_name": query.pod_name,
            "events": [
                {
                    "type": "Normal",
                    "reason": "Scheduled",
                    "message": f"Successfully assigned {query.namespace}/{query.pod_name} to node",
                },
                {
                    "type": "Normal",
                    "reason": "Pulled",
                    "message": "Container image pulled successfully",
                },
                {"type": "Normal", "reason": "Created", "message": "Created container app"},
            ],
        },
    )


def gke_deployment_get(query: DeploymentGetQuery, tenant_id: str) -> ToolResult:
    return ToolResult(
        status="ok",
        data={
            "tenant_id": tenant_id,
            "provider": CloudProvider.GCP,
            "project_id": query.project_id,
            "cluster": query.cluster,
            "namespace": query.namespace,
            "deployment_name": query.deployment_name,
            "replicas": 3,
            "available_replicas": 3,
            "updated_replicas": 3,
            "strategy": "RollingUpdate",
        },
    )


def gke_node_get(query: NodeGetQuery, tenant_id: str) -> ToolResult:
    return ToolResult(
        status="ok",
        data={
            "tenant_id": tenant_id,
            "provider": CloudProvider.GCP,
            "project_id": query.project_id,
            "cluster": query.cluster,
            "node_name": query.node_name,
            "status": "Ready",
            "kubelet_version": "v1.28.3-gke.1000",
            "capacity": {"cpu": "8", "memory": "32Gi"},
            "allocatable": {"cpu": "7.8", "memory": "30Gi"},
        },
    )


def gke_metrics_get(query: MetricsGetQuery, tenant_id: str) -> ToolResult:
    return ToolResult(
        status="ok",
        data={
            "tenant_id": tenant_id,
            "provider": CloudProvider.GCP,
            "project_id": query.project_id,
            "cluster": query.cluster,
            "resource_kind": query.resource_kind,
            "resource_name": query.resource_name,
            "metrics": {
                "cpu_usage_cores": 0.45,
                "memory_usage_bytes": 1073741824,
                "network_rx_bytes": 5242880,
                "network_tx_bytes": 2097152,
            },
        },
    )


# --- Legacy Handlers ---


def list_resources(query: InventoryQuery, tenant_id: str) -> ToolResult:
    return ToolResult(
        status="ok",
        data={
            "tenant_id": tenant_id,
            "environment": query.environment,
            "accounts": [
                {"provider": "aws", "account_id": "demo-account", "name": "platform-prod"}
            ],
            "regions": ["us-east-1"],
            "services": ["checkout-api", "orders"],
            "dependencies": [{"source": "checkout-api", "target": "orders", "type": "database"}],
            "resources": [
                {
                    "resource_id": "i-demo-001",
                    "provider": "aws",
                    "kind": "compute",
                    "name": "checkout-api-node-01",
                    "service": "checkout-api",
                    "region": "us-east-1",
                    "environment": query.environment,
                    "status": "running",
                },
            ],
        },
    )


def get_pods(query: PodQuery, tenant_id: str) -> ToolResult:
    return ToolResult(
        status="ok",
        data={
            "tenant_id": tenant_id,
            "namespace": query.namespace,
            "pods": [
                {"name": "checkout-api-7b9c8d6f6b-abc12", "phase": "Running", "restarts": 0},
                {"name": "checkout-api-7b9c8d6f6b-def34", "phase": "Running", "restarts": 1},
            ],
        },
    )


def restart_pod(command: RestartPodRequest, tenant_id: str) -> ToolResult:
    return ToolResult(
        status="mock_executed",
        data={
            "tenant_id": tenant_id,
            "namespace": command.namespace,
            "pod_name": command.pod_name,
            "action": "restart",
        },
    )


def scale_deployment(command: ScaleDeploymentRequest, tenant_id: str) -> ToolResult:
    return ToolResult(
        status="mock_executed",
        data={
            "tenant_id": tenant_id,
            "namespace": command.namespace,
            "deployment": command.deployment,
            "replicas": command.replicas,
            "action": "scale",
        },
    )


def rollback_deployment(command: RollbackDeploymentRequest, tenant_id: str) -> ToolResult:
    return ToolResult(
        status="mock_executed",
        data={
            "tenant_id": tenant_id,
            "namespace": command.namespace,
            "deployment": command.deployment,
            "revision": command.revision,
            "action": "rollback",
        },
    )


def get_incident_signals(query: IncidentSignalsQuery, tenant_id: str) -> ToolResult:
    return ToolResult(
        status="ok",
        data={
            "tenant_id": tenant_id,
            "service": query.service,
            "latency_p95_ms": 840,
            "error_rate_percent": 8.4,
            "cpu_percent": 91,
            "database_pool_utilization_percent": 96,
            "window": "last_30_minutes",
        },
    )


def get_security_events(query: SecurityEventsQuery, tenant_id: str) -> ToolResult:
    return ToolResult(
        status="ok",
        data={
            "tenant_id": tenant_id,
            "events": [
                {
                    "event_type": "policy_violation",
                    "title": "Production role assumed from an untrusted network",
                    "resource_id": "role/checkout-deployer",
                    "actor": "svc-deployer",
                    "occurred_at": "2026-09-22T14:02:00+00:00",
                    "severity": 4,
                    "source": "cloudtrail.mock",
                    "details": {"environment": query.environment, "policy": "trusted-network"},
                }
            ],
        },
    )


def default_tools() -> list[ToolSpec]:
    return [
        # --- GKE Read-Only Tools ---
        ToolSpec(
            name="gke.pod.get",
            description="Get metadata for a specific GKE Pod.",
            category=ToolCategory.KUBERNETES,
            provider=CloudProvider.GCP,
            version="1.0",
            risk=ToolRisk.READ_ONLY,
            required_permission="tools:read",
            input_model=PodGetQuery,
            handler=gke_pod_get,
        ),
        ToolSpec(
            name="gke.pod.describe",
            description="Describe detailed status and spec for a GKE Pod.",
            category=ToolCategory.KUBERNETES,
            provider=CloudProvider.GCP,
            version="1.0",
            risk=ToolRisk.READ_ONLY,
            required_permission="tools:read",
            input_model=PodDescribeQuery,
            handler=gke_pod_describe,
        ),
        ToolSpec(
            name="gke.pod.logs",
            description="Fetch recent container logs from a GKE Pod.",
            category=ToolCategory.KUBERNETES,
            provider=CloudProvider.GCP,
            version="1.0",
            risk=ToolRisk.READ_ONLY,
            required_permission="tools:read",
            input_model=PodLogsQuery,
            handler=gke_pod_logs,
        ),
        ToolSpec(
            name="gke.pod.events",
            description="List Kubernetes events associated with a GKE Pod.",
            category=ToolCategory.KUBERNETES,
            provider=CloudProvider.GCP,
            version="1.0",
            risk=ToolRisk.READ_ONLY,
            required_permission="tools:read",
            input_model=PodEventsQuery,
            handler=gke_pod_events,
        ),
        ToolSpec(
            name="gke.deployment.get",
            description="Get GKE Deployment status and replica metrics.",
            category=ToolCategory.KUBERNETES,
            provider=CloudProvider.GCP,
            version="1.0",
            risk=ToolRisk.READ_ONLY,
            required_permission="tools:read",
            input_model=DeploymentGetQuery,
            handler=gke_deployment_get,
        ),
        ToolSpec(
            name="gke.node.get",
            description="Get GKE cluster node status and resource allocation.",
            category=ToolCategory.KUBERNETES,
            provider=CloudProvider.GCP,
            version="1.0",
            risk=ToolRisk.READ_ONLY,
            required_permission="tools:read",
            input_model=NodeGetQuery,
            handler=gke_node_get,
        ),
        ToolSpec(
            name="gke.metrics.get",
            description="Retrieve CPU, memory, and network metrics for GKE resources.",
            category=ToolCategory.OBSERVABILITY,
            provider=CloudProvider.GCP,
            version="1.0",
            risk=ToolRisk.READ_ONLY,
            required_permission="tools:read",
            input_model=MetricsGetQuery,
            handler=gke_metrics_get,
        ),
        # --- Legacy / Multi-Cloud Tools ---
        ToolSpec(
            name="inventory.list_resources",
            description="List normalized resources visible in an environment.",
            category=ToolCategory.CLOUD,
            provider=CloudProvider.AWS,
            risk=ToolRisk.READ_ONLY,
            required_permission="tools:read",
            input_model=InventoryQuery,
            handler=list_resources,
        ),
        ToolSpec(
            name="kubernetes.get_pods",
            description="List pods and restart counts in a namespace.",
            category=ToolCategory.KUBERNETES,
            provider=CloudProvider.AWS,
            risk=ToolRisk.READ_ONLY,
            required_permission="tools:read",
            input_model=PodQuery,
            handler=get_pods,
        ),
        ToolSpec(
            name="kubernetes.restart_pod",
            description="Restart a named pod through the controlled mock adapter.",
            category=ToolCategory.KUBERNETES,
            provider=CloudProvider.AWS,
            risk=ToolRisk.MEDIUM_RISK,
            required_permission="tools:execute",
            input_model=RestartPodRequest,
            handler=restart_pod,
        ),
        ToolSpec(
            name="kubernetes.scale_deployment",
            description="Request a deployment replica change.",
            category=ToolCategory.KUBERNETES,
            provider=CloudProvider.AWS,
            risk=ToolRisk.HIGH_RISK,
            required_permission="tools:execute",
            input_model=ScaleDeploymentRequest,
            handler=scale_deployment,
        ),
        ToolSpec(
            name="kubernetes.rollback_deployment",
            description="Roll back a deployment to a specified revision.",
            category=ToolCategory.KUBERNETES,
            provider=CloudProvider.AWS,
            risk=ToolRisk.CRITICAL,
            required_permission="tools:execute",
            input_model=RollbackDeploymentRequest,
            handler=rollback_deployment,
        ),
        ToolSpec(
            name="observability.get_incident_signals",
            description="Collect mock metrics for a service incident window.",
            category=ToolCategory.OBSERVABILITY,
            provider=CloudProvider.AWS,
            risk=ToolRisk.READ_ONLY,
            required_permission="tools:read",
            input_model=IncidentSignalsQuery,
            handler=get_incident_signals,
        ),
        ToolSpec(
            name="security.get_events",
            description="Collect mock IAM and policy security events.",
            category=ToolCategory.CLOUD,
            provider=CloudProvider.AWS,
            risk=ToolRisk.READ_ONLY,
            required_permission="tools:read",
            input_model=SecurityEventsQuery,
            handler=get_security_events,
        ),
    ]
