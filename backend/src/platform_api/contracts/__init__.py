"""Platform contracts package exposing canonical Pydantic v2 schemas."""

from platform_api.contracts.agent import (
    AgentInputScope,
    AgentRunState,
    AgentStepState,
    SharedAgentResultContract,
)
from platform_api.contracts.api import APIResponse, ResponseMetadata
from platform_api.contracts.approval import ApprovalRequest, ApprovalStatus
from platform_api.contracts.audit import ConsequentialAuditRecord
from platform_api.contracts.domain import (
    CloudProvider,
    Environment,
    IncidentSeverity,
    ResourceCategory,
    StatementClassification,
    WorkflowStatus,
)
from platform_api.contracts.errors import ErrorCode, ErrorDetail
from platform_api.contracts.evidence import (
    EvidenceItem,
    EvidenceScope,
    EvidenceTimeWindow,
    FindingItem,
    RecommendationItem,
)
from platform_api.contracts.identity import Principal, TenantContext
from platform_api.contracts.llm import (
    ChatMessage,
    LLMRequest,
    LLMResponse,
    MessageRole,
    ModelAlias,
)
from platform_api.contracts.mcp import (
    ToolCategory,
    ToolRequest,
    ToolResponse,
    ToolRisk,
    ToolSpec,
)
from platform_api.contracts.pagination import PageParams, PaginatedResponse
from platform_api.contracts.policy import PolicyDecision, RiskLevel
from platform_api.contracts.remediation import (
    PreconditionCheck,
    RemediationPlan,
    RemediationStatus,
)
from platform_api.contracts.simulation import BlastRadius, SimulationResult, StateDelta
from platform_api.contracts.verification import (
    SignalCheck,
    VerificationClass,
    VerificationResult,
)

__all__ = [
    "APIResponse",
    "AgentInputScope",
    "AgentRunState",
    "AgentStepState",
    "ApprovalRequest",
    "ApprovalStatus",
    "BlastRadius",
    "ChatMessage",
    "CloudProvider",
    "ConsequentialAuditRecord",
    "Environment",
    "ErrorCode",
    "ErrorDetail",
    "EvidenceItem",
    "EvidenceScope",
    "EvidenceTimeWindow",
    "FindingItem",
    "IncidentSeverity",
    "LLMRequest",
    "LLMResponse",
    "MessageRole",
    "ModelAlias",
    "PageParams",
    "PaginatedResponse",
    "PolicyDecision",
    "PreconditionCheck",
    "Principal",
    "RecommendationItem",
    "RemediationPlan",
    "RemediationStatus",
    "ResourceCategory",
    "ResponseMetadata",
    "RiskLevel",
    "SharedAgentResultContract",
    "SignalCheck",
    "SimulationResult",
    "StateDelta",
    "StatementClassification",
    "TenantContext",
    "ToolCategory",
    "ToolRequest",
    "ToolResponse",
    "ToolRisk",
    "ToolSpec",
    "VerificationClass",
    "VerificationResult",
    "WorkflowStatus",
]
