from typing import Literal, TypedDict

AgentRoute = Literal[
    "discovery",
    "sre",
    "investigation",
    "change",
    "finops",
    "security",
    "mlops",
    "llmops",
    "remediation",
    "governance",
]


class StructuredFinding(TypedDict, total=False):
    category: Literal["OBSERVED", "INFERRED", "RECOMMENDED"]
    description: str
    evidence_ids: list[str]


class HypothesisItem(TypedDict, total=False):
    hypothesis: str
    confidence: float
    evidence_ids: list[str]


class AgentState(TypedDict, total=False):
    run_id: str
    tenant_id: str
    subject: str
    permissions: list[str]
    request: str
    request_type: AgentRoute
    next_agent: AgentRoute
    cloud_provider: str
    environment: str
    account_id: str
    region: str
    target_resource: str
    namespace: str
    cluster: str
    project_id: str
    deployment: str
    workspace_project_id: str
    workspace_environment_id: str
    status: Literal[
        "queued",
        "pending",
        "running",
        "completed",
        "partial",
        "failed",
        "cancelled",
        "awaiting_approval",
        "paused",
        "started",
    ]
    correlation_id: str
    trace_id: str
    evidence: list[dict[str, object]]
    structured_findings: list[StructuredFinding]
    findings: list[str]
    hypotheses: list[HypothesisItem]
    confidence: float
    disagreements: list[str]
    missing_evidence: list[str]
    recommendation: str
    recommendations: list[str]
    approval_required: bool
    approval_id: str
    error: str
    inventory_count: int
    initial_evidence: list[dict[str, object]]
    steps: list[dict[str, object]]
    retry_count: int
    max_retries: int
