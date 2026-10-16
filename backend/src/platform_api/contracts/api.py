"""Generic API response envelope contracts."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from platform_api.contracts.errors import ErrorDetail


class ResponseMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(max_length=100)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: str = Field(default="v1", max_length=10)


class APIResponse[T](BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    data: T | None = None
    error: ErrorDetail | None = None
    meta: ResponseMetadata
