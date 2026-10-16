"""Approval request and action hash binding contracts."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from platform_api.contracts.policy import RiskLevel


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = Field(min_length=1, max_length=100)
    approver_id: str | None = Field(default=None, max_length=100)
    requester_id: str = Field(min_length=1, max_length=100)
    run_id: str = Field(min_length=1, max_length=100)
    tool_name: str = Field(min_length=1, max_length=200)
    resource_ids: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    parameters_hash: str = Field(min_length=1, max_length=128)
    risk_level: RiskLevel
    policy_version: str = Field(default="v1.0", max_length=50)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(minutes=30))
    decided_at: datetime | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    single_use: Literal[True] = True
