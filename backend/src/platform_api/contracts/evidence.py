"""Evidence, Finding, and Recommendation contracts."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from platform_api.contracts.domain import CloudProvider, StatementClassification
from platform_api.contracts.policy import RiskLevel


class EvidenceScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(min_length=1, max_length=100)
    service_id: str = Field(min_length=1, max_length=100)
    environment: str = Field(default="production", max_length=50)
    account_id: str = Field(default="default", max_length=100)


class EvidenceTimeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: datetime
    end: datetime


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=50)
    source: str = Field(min_length=1, max_length=100)
    provider: CloudProvider
    resource_id: str = Field(min_length=1, max_length=200)
    scope: EvidenceScope
    window: EvidenceTimeWindow | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    value: Any = None
    query_ref: str = Field(default="direct", max_length=500)
    tool_call_id: str | None = None
    classification: StatementClassification = StatementClassification.OBSERVED


class FindingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(min_length=1, max_length=100)
    classification: StatementClassification
    statement: str = Field(min_length=1, max_length=5_000)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: str | None = None


class RecommendationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str = Field(min_length=1, max_length=100)
    rationale: str = Field(min_length=1, max_length=5_000)
    target_resource: str = Field(min_length=1, max_length=200)
    expected_outcome: str = Field(min_length=1, max_length=1_000)
    proposed_action: str = Field(min_length=1, max_length=200)
    tool_name: str = Field(min_length=1, max_length=200)
    tool_parameters: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel
    reversibility: bool = True
    expires_at: datetime
    required_approval: bool = True
    verification_criteria: list[str] = Field(default_factory=list)
