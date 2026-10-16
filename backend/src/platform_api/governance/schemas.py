"""Governance and approval schemas re-exported from platform_api.contracts."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from platform_api.contracts.approval import ApprovalStatus
from platform_api.contracts.policy import RiskLevel as ToolRisk


class PolicyDecision(BaseModel):
    allowed: bool
    require_human_approval: bool
    reason: str
    risk: ToolRisk


class ApprovalRequestCreate(BaseModel):
    action: str = Field(min_length=1, max_length=200)
    tool_name: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=5_000)
    risk: ToolRisk
    affected_resources: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    run_id: str | None = None
    expires_in_minutes: int = Field(default=30, ge=1, le=1_440)
    target_resource_hash: str | None = None
    policy_version: str = Field(default="v1.0.0")
    required_evidence_count: int = Field(default=1, ge=1)


class ApprovalRequest(ApprovalRequestCreate):
    id: str
    tenant_id: str
    requester: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    approver: str | None = None
    decision_reason: str | None = None
    created_at: datetime
    expires_at: datetime
    decided_at: datetime | None = None
    single_use: bool = True
    consumed: bool = False
    consumed_at: datetime | None = None


def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(UTC)


def expiration(minutes: int) -> datetime:
    return now() + timedelta(minutes=minutes)


__all__ = [
    "ApprovalRequest",
    "ApprovalRequestCreate",
    "ApprovalStatus",
    "PolicyDecision",
    "ToolRisk",
    "expiration",
    "new_id",
    "now",
]
