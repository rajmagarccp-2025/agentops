"""Verification engine status and signal check contracts."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VerificationClass(StrEnum):
    RECOVERED = "RECOVERED"
    PARTIALLY_RECOVERED = "PARTIALLY_RECOVERED"
    NOT_RECOVERED = "NOT_RECOVERED"
    REGRESSION = "REGRESSION"
    UNKNOWN = "UNKNOWN"


class SignalCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_name: str = Field(min_length=1, max_length=100)
    metric_or_health_check: str = Field(min_length=1, max_length=200)
    expected: Any = None
    actual: Any = None
    passed: bool


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_id: str = Field(min_length=1, max_length=100)
    remediation_id: str = Field(min_length=1, max_length=100)
    tenant_id: str = Field(min_length=1, max_length=100)
    status: VerificationClass
    post_action_state: dict[str, Any] = Field(default_factory=dict)
    signals_checked: list[SignalCheck] = Field(default_factory=list)
    service_health_acceptable: bool = False
    verified_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reconciliation_notes: str | None = None
