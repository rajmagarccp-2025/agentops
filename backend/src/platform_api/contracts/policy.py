"""Policy and Risk decision contracts."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from platform_api.contracts.mcp import ToolRisk

RiskLevel = ToolRisk


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    decision_id: str = Field(default="dec-default", max_length=100)
    decision: Literal["allow", "deny", "approval_required"] = "allow"
    allowed: bool = True
    require_human_approval: bool = False
    risk: RiskLevel = Field(
        default=RiskLevel.READ_ONLY,
        validation_alias=AliasChoices("risk", "risk_level"),
    )
    reason: str = Field(min_length=1, max_length=5_000)
    policy_version: str = Field(default="v1.0", max_length=50)
    rule_id: str = Field(default="default-rule", max_length=100)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    execution_time_recheck_required: bool = True

    @property
    def risk_level(self) -> RiskLevel:
        return self.risk


__all__ = ["PolicyDecision", "RiskLevel", "ToolRisk"]
