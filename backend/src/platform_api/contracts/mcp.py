"""MCP Tool and Gateway execution contracts."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from platform_api.contracts.domain import CloudProvider


class ToolRisk(StrEnum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"
    CRITICAL = "CRITICAL"


class ToolCategory(StrEnum):
    CLOUD = "cloud"
    KUBERNETES = "kubernetes"
    OBSERVABILITY = "observability"
    ITSM = "itsm"
    CICD = "cicd"


class ToolSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    version: str = Field(default="1.0", max_length=20)
    purpose: str = Field(min_length=1, max_length=1_000)
    provider: CloudProvider
    operation_type: Literal["read", "mutation"]
    required_permissions: list[str] = Field(default_factory=list)
    tenant_scope: bool = True
    resource_scope: str = Field(default="tenant", max_length=100)
    risk_level: ToolRisk
    timeout_ms: int = Field(default=30_000, ge=1_000, le=300_000)
    retry_enabled: bool = False
    idempotent: bool = True
    supports_dry_run: bool = True
    audit_level: Literal["standard", "consequential"] = "standard"


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(default="", max_length=200)
    version: str = Field(default="1.0", max_length=20)
    parameters: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = Field(default="", max_length=100)
    request_id: str = Field(default="", max_length=100)
    dry_run: bool = False
    risk_level: ToolRisk = ToolRisk.READ_ONLY
    idempotency_key: str | None = Field(default=None, max_length=128)


class ToolResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: str = Field(min_length=1, max_length=100)
    status: Literal["executed", "dry_run", "validation_failed", "approval_required", "failed"]
    tool_name: str = Field(min_length=1, max_length=200)
    risk_level: ToolRisk
    tenant_id: str = Field(min_length=1, max_length=100)
    result_data: dict[str, Any] | None = None
    validation_errors: list[dict[str, Any]] | None = None
    provider_operation_id: str | None = Field(default=None, max_length=200)
