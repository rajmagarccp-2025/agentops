"""Standardized platform error code and detail schemas."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    STALE_STATE = "stale_state"
    RATE_LIMITED = "rate_limited"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    TIMEOUT = "timeout"
    POLICY_DENIED = "policy_denied"
    APPROVAL_REQUIRED = "approval_required"
    INTERNAL_FAILURE = "internal_failure"


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    message: str = Field(min_length=1, max_length=5_000)
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str = Field(default="unknown", max_length=100)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
