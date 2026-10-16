"""Remediation action, precondition check, and plan contracts."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RemediationStatus(StrEnum):
    DRAFT = "draft"
    SIMULATED = "simulated"
    AWAITING_APPROVAL = "awaiting_approval"
    PENDING_EXECUTION = "pending_execution"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    RECONCILING = "reconciling"


class PreconditionCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str = Field(min_length=1, max_length=100)
    target_resource: str = Field(min_length=1, max_length=200)
    condition: str = Field(min_length=1, max_length=500)
    passed: bool
    observed_value: Any = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RemediationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remediation_id: str = Field(min_length=1, max_length=100)
    recommendation_id: str = Field(min_length=1, max_length=100)
    tenant_id: str = Field(min_length=1, max_length=100)
    target_resource: str = Field(min_length=1, max_length=200)
    allowlisted_tool: str = Field(min_length=1, max_length=200)
    proposed_parameters: dict[str, Any] = Field(default_factory=dict)
    preconditions: list[PreconditionCheck] = Field(default_factory=list)
    simulation_id: str | None = Field(default=None, max_length=100)
    approval_id: str | None = Field(default=None, max_length=100)
    status: RemediationStatus = RemediationStatus.DRAFT
    provider_operation_id: str | None = Field(default=None, max_length=200)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
