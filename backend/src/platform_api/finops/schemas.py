from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RecommendationType(StrEnum):
    RIGHTSIZE = "rightsizing"
    IDLE_RESOURCE = "idle_resource"
    COST_ANOMALY = "cost_anomaly"


class CostRecordCreate(BaseModel):
    period: date
    provider: str = Field(min_length=1, max_length=50)
    account: str = Field(min_length=1, max_length=200)
    service: str = Field(min_length=1, max_length=200)
    environment: str = Field(min_length=1, max_length=100)
    amount_usd: float = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CostRecord(CostRecordCreate):
    id: str
    tenant_id: str


class UtilizationCreate(BaseModel):
    observed_on: date
    resource_id: str = Field(min_length=1, max_length=255)
    service: str = Field(min_length=1, max_length=200)
    environment: str = Field(min_length=1, max_length=100)
    cpu_percent: float = Field(ge=0, le=100)
    memory_percent: float = Field(ge=0, le=100)
    monthly_cost_usd: float = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UtilizationRecord(UtilizationCreate):
    id: str
    tenant_id: str


class RecommendationCategory(StrEnum):
    RIGHTSIZE = "rightsizing"
    CLEANUP = "cleanup"
    SCHEDULING = "scheduling"
    COMMITMENT = "commitment"
    COST_ANOMALY = "cost_anomaly"


class SavingsRecommendation(BaseModel):
    id: str
    tenant_id: str
    recommendation_type: RecommendationType
    category: RecommendationCategory = RecommendationCategory.RIGHTSIZE
    resource_id: str | None
    service: str
    title: str
    rationale: str
    current_capacity: str = Field(description="Current capacity or provisioning spec")
    proposed_capacity: str = Field(description="Proposed capacity or provisioning spec")
    estimated_monthly_savings_usd: float = Field(ge=0)
    savings_formula: str = Field(description="Formula used to calculate financial savings")
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    risks: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    expiry: str = Field(description="ISO timestamp or date when recommendation expires")
    requires_approval: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class FinOpsRecommendation(SavingsRecommendation):
    pass


class FinOpsSummary(BaseModel):
    total_cost_usd: float
    cost_by_service: dict[str, float]
    utilization_records: int
    anomaly_count: int
    forecast_next_month_usd: float
    recommendations: list[FinOpsRecommendation]
