from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from platform_api.contracts.mcp import ToolRisk


class RemediationAction(StrEnum):
    RESTART_POD = "kubernetes.restart_pod"
    SCALE_DEPLOYMENT = "kubernetes.scale_deployment"
    ROLLBACK_DEPLOYMENT = "kubernetes.rollback_deployment"


class RemediationRequest(BaseModel):
    action: RemediationAction
    parameters: dict[str, Any] = Field(default_factory=dict)
    target_resource: str = Field(default="default_resource", max_length=200)
    user_confirmed: bool = Field(default=True)
    dry_run: bool = False
    idempotency_key: str = Field(min_length=8, max_length=200)
    approval_id: str | None = None
    run_id: str | None = None


class ActionPreviewResponse(BaseModel):
    action: RemediationAction
    target_resource: str
    risk_level: ToolRisk
    current_state: dict[str, Any]
    proposed_state: dict[str, Any]
    requires_approval: bool
    policy_decision: str
    simulation_result: dict[str, Any]


class RemediationRecord(BaseModel):
    id: str
    tenant_id: str
    user_subject: str
    action: RemediationAction
    parameters: dict[str, Any]
    target_resource: str
    user_confirmed: bool
    status: str
    risk_level: ToolRisk
    execution_id: str | None
    provider_operation_id: str | None = None
    idempotency_key: str
    policy_version: str = "v1.0"
    created_at: datetime
    verified: bool = False
    verification_message: str | None = None


def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(UTC)
