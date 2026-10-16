from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class PromptVersionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=50)
    template: str = Field(min_length=1, max_length=100_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptVersion(PromptVersionCreate):
    id: str
    tenant_id: str
    created_at: datetime


class EvaluationCreate(BaseModel):
    dataset: str = Field(min_length=1, max_length=200)
    prompt_version_id: str | None = None
    model: str = Field(min_length=1, max_length=150)
    input_text: str = Field(min_length=1, max_length=20_000)
    output_text: str = Field(min_length=1, max_length=100_000)
    expected_text: str | None = None
    grounded: bool = True
    tool_call_correct: bool = True
    retrieval_quality: float = Field(default=1.0, ge=0, le=1)
    latency_ms: float = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0, ge=0)


class LLMOpsFinding(BaseModel):
    category: str = Field(description="OBSERVED / INFERRED / RECOMMENDED")
    metric: str = Field(
        description="Target metric monitored: latency, tokens, cost, retrieval, errors, regression"
    )
    description: str
    impact: str
    evidence_ids: list[str] = Field(default_factory=list)


class LLMOpsTelemetryReport(BaseModel):
    model_alias: str
    provider: str
    model_name: str
    prompt_version: str
    latency_p50_ms: float
    latency_p99_ms: float
    prompt_tokens_24h: int
    completion_tokens_24h: int
    total_tokens_24h: int
    total_cost_usd_24h: float
    retrieval_precision: float
    retrieval_recall: float
    tool_call_accuracy: float
    error_rate: float
    regression_detected: bool
    regression_details: str | None = None


class EvaluationResult(BaseModel):
    id: str
    tenant_id: str
    dataset: str
    model: str
    correctness: float
    groundedness: float
    retrieval_quality: float
    tool_call_correctness: float
    latency_ms: float
    estimated_cost_usd: float
    success: bool
    created_at: datetime


class LLMOpsMonitoringResult(BaseModel):
    tenant_id: str
    target_resource: str
    telemetry_reports: list[LLMOpsTelemetryReport]
    evaluations: list[EvaluationResult]
    prompt_versions: list[PromptVersion]
    findings: list[LLMOpsFinding]
    recommendations: list[str]
    confidence: float = Field(default=0.88, ge=0, le=1)
    hypotheses: list[dict[str, Any]]


# --- Multi-Model Gateway & Security Schemas ---

ProviderType = Literal[
    "openai", "azure_openai", "anthropic", "google_gemini", "aws_bedrock", "custom_openai", "mock"
]
ModelStatus = Literal["active", "disabled", "archived"]
PermissionType = Literal["use", "view_metadata", "manage_access", "manage_model", "view_usage"]
GranteeType = Literal["user", "group", "public_org"]
PolicyEffect = Literal["allow", "deny"]


class RegisteredModelCreate(BaseModel):
    provider: ProviderType
    model_name: str = Field(min_length=1, max_length=150)
    display_name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    api_key: str = Field(
        min_length=1, description="API Key or credential string, stored securely in Secrets Manager"
    )
    base_url: str | None = None
    api_version: str | None = None
    tags: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=lambda: ["chat", "structured_output"])
    provider_config: dict[str, Any] = Field(default_factory=dict)
    project_ids: list[str] = Field(
        default_factory=list, description="Explicit project availability scope"
    )
    environment_ids: list[str] = Field(
        default_factory=list, description="Explicit environment availability scope"
    )
    organization_wide: bool = Field(
        default=True, description="Available organization-wide subject to policies"
    )
    test_connection_first: bool = Field(
        default=True, description="Test connection before finalizing model registration"
    )


class RegisteredModelUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    status: ModelStatus | None = None
    base_url: str | None = None
    api_version: str | None = None
    tags: list[str] | None = None
    capabilities: list[str] | None = None
    provider_config: dict[str, Any] | None = None
    project_ids: list[str] | None = None
    environment_ids: list[str] | None = None


class CredentialRotateRequest(BaseModel):
    api_key: str = Field(min_length=1, description="New API key or secret to rotate to")
    test_connection: bool = Field(default=True, description="Verify new key before rotation")


class RegisteredModelResponse(BaseModel):
    id: str
    tenant_id: str
    provider: str
    model_name: str
    display_name: str
    description: str
    tags: list[str]
    capabilities: list[str]
    status: str
    base_url: str | None = None
    api_version: str | None = None
    provider_config: dict[str, Any]
    credential_status: str = "configured"  # configured, missing, error
    credential_masked: str = "●●●●●●●●"
    created_by: str
    is_administrator: bool = False
    effective_permissions: list[str] = Field(default_factory=list)
    project_ids: list[str] = Field(default_factory=list)
    environment_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ModelAdminAssignRequest(BaseModel):
    user_id: str = Field(
        min_length=1, description="User ID to assign or remove as model administrator"
    )


class ModelAdminResponse(BaseModel):
    id: str
    model_id: str
    user_id: str
    assigned_by: str
    created_at: datetime


class ModelAccessPolicyCreate(BaseModel):
    grantee_type: GranteeType
    grantee_id: str | None = Field(
        default=None, description="User ID or Group ID (null for public_org)"
    )
    project_id: str | None = None
    environment_id: str | None = None
    permission: PermissionType = "use"
    effect: PolicyEffect = "allow"


class ModelAccessPolicyResponse(BaseModel):
    id: str
    model_id: str
    organization_id: str
    project_id: str | None
    environment_id: str | None
    grantee_type: str
    grantee_id: str | None
    permission: str
    effect: str
    created_by: str
    created_at: datetime


class TestCredentialRequest(BaseModel):
    provider: ProviderType
    model_name: str
    api_key: str
    base_url: str | None = None
    api_version: str | None = None
    provider_config: dict[str, Any] = Field(default_factory=dict)


class TestConnectionResponse(BaseModel):
    success: bool
    latency_ms: float
    provider: str
    model_name: str
    message: str


# --- Gateway Chat Completion Schemas ---


class GatewayChatMessage(BaseModel):
    role: str  # system, user, assistant, tool
    content: str
    name: str | None = None


class GatewayChatCompletionRequest(BaseModel):
    model: str = Field(description="Internal RegisteredModel ID or model_name")
    messages: list[GatewayChatMessage]
    organization_id: str | None = Field(
        default=None, description="Target tenant/org ID (validated against token)"
    )
    project_id: str | None = Field(default=None, description="Target project ID scope")
    environment_id: str | None = Field(default=None, description="Target environment ID scope")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=1000, ge=1)
    top_p: float | None = Field(default=1.0)
    stream: bool = False
    response_format: str | None = Field(default=None, description="json or text")


class GatewayChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str


class GatewayChoice(BaseModel):
    index: int = 0
    message: GatewayChoiceMessage
    finish_reason: str = "stop"


class GatewayUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class GatewayChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    provider: str
    choices: list[GatewayChoice]
    usage: GatewayUsage
    estimated_cost_usd: float
    latency_ms: float


# --- Group Schemas ---


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=100)
    description: str = Field(default="", max_length=500)


class GroupResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    slug: str
    description: str
    member_count: int = 0
    created_at: datetime


class UserGroupMemberCreate(BaseModel):
    user_id: str
