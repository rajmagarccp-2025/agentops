"""Agent input, output, and execution state contracts."""

from datetime import UTC, datetime
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field

from platform_api.contracts.domain import CloudProvider, Environment, WorkflowStatus
from platform_api.contracts.evidence import EvidenceItem, FindingItem, RecommendationItem


class AgentInputScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=255)
    permissions: list[str] = Field(default_factory=list)
    cloud_provider: CloudProvider = CloudProvider.AWS
    environment: Environment = Environment.PRODUCTION
    account_id: str = Field(default="default", max_length=100)
    region: str = Field(default="us-east-1", max_length=50)
    target_resource: str = Field(default="system", max_length=200)
    time_window_start: datetime | None = None
    time_window_end: datetime | None = None


class SharedAgentResultContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1, max_length=100)
    tenant_id: str = Field(min_length=1, max_length=100)
    agent_id: str = Field(min_length=1, max_length=100)
    status: WorkflowStatus
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    input_scope: AgentInputScope
    evidence: list[EvidenceItem] = Field(default_factory=list)
    findings: list[FindingItem] = Field(default_factory=list)
    recommendations: list[RecommendationItem] = Field(default_factory=list)
    confidence: dict[str, float] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class AgentStepState(TypedDict, total=False):
    agent: str
    timestamp: str
    status: str
    next_agent: str
    approver: str
    approval_required: bool
    approval_id: str
    error: str
    evidence: list[dict[str, Any]]
    findings: list[str]
    recommendation: str


class AgentRunState(TypedDict, total=False):
    run_id: str
    tenant_id: str
    subject: str
    permissions: list[str]
    request: str
    request_type: str
    next_agent: str
    cloud_provider: str
    environment: str
    account_id: str
    region: str
    target_resource: str
    status: str
    checkpoint_id: str
    step_index: int
    correlation_id: str
    trace_id: str
    evidence: list[dict[str, Any]]
    findings: list[str]
    recommendation: str
    approval_required: bool
    approval_id: str
    error: str
    inventory_count: int
    initial_evidence: list[dict[str, Any]]
    steps: list[AgentStepState]
