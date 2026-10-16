"""Consequential audit logging payload contracts."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from platform_api.contracts.policy import RiskLevel


class ConsequentialAuditRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_id: str = Field(min_length=1, max_length=100)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tenant_id: str = Field(min_length=1, max_length=100)
    principal_subject: str = Field(min_length=1, max_length=255)
    request_id: str = Field(min_length=1, max_length=100)
    run_id: str = Field(min_length=1, max_length=100)
    agent_id: str = Field(min_length=1, max_length=100)
    agent_version: str = Field(default="v1.0", max_length=50)
    prompt_version: str = Field(default="v1.0", max_length=50)
    model_provider: str = Field(min_length=1, max_length=100)
    evidence_ids: list[str] = Field(default_factory=list)
    tool_name: str = Field(min_length=1, max_length=200)
    tool_parameters_digest: str = Field(min_length=1, max_length=128)
    policy_decision_id: str = Field(min_length=1, max_length=100)
    risk_level: RiskLevel
    approval_id: str | None = Field(default=None, max_length=100)
    executed_parameters_digest: str = Field(min_length=1, max_length=128)
    before_state_summary: dict[str, Any] = Field(default_factory=dict)
    after_state_summary: dict[str, Any] = Field(default_factory=dict)
    provider_operation_id: str | None = Field(default=None, max_length=200)
    verification_status: str | None = Field(default=None, max_length=50)
