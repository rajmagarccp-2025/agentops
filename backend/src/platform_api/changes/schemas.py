from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ChangeType(StrEnum):
    DEPLOYMENT = "deployment"
    CONFIGURATION = "configuration"
    IAC = "iac"
    PLATFORM = "platform"
    INFRASTRUCTURE = "infrastructure"


class ChangeEventCreate(BaseModel):
    service: str = Field(min_length=1, max_length=200)
    environment: str = Field(min_length=1, max_length=100)
    change_type: ChangeType
    title: str = Field(min_length=1, max_length=300)
    occurred_at: datetime
    source: str = Field(min_length=1, max_length=200)
    actor: str | None = Field(default=None, max_length=200)
    affected_resources: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class ChangeEvent(ChangeEventCreate):
    id: str
    tenant_id: str


class ChangeCorrelationResult(BaseModel):
    tenant_id: str
    target_service: str
    changes: list[ChangeEvent]
    affected_resources: list[str]
    timestamps: list[str]
    evidence: list[dict[str, Any]]
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    uncertainty: str
    correlation_confidence: float = 0.0
