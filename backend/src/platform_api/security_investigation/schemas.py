from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SecurityEventType(StrEnum):
    IAM = "iam"
    POLICY_VIOLATION = "policy_violation"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    VULNERABILITY = "vulnerability"


class SecurityEventCreate(BaseModel):
    event_type: SecurityEventType
    title: str = Field(min_length=1, max_length=300)
    service: str | None = Field(default=None, max_length=200)
    resource_id: str | None = Field(default=None, max_length=255)
    actor: str | None = Field(default=None, max_length=200)
    occurred_at: datetime
    severity: int = Field(ge=1, le=5)
    source: str = Field(min_length=1, max_length=200)
    details: dict[str, Any] = Field(default_factory=dict)


class SecurityEvent(SecurityEventCreate):
    id: str
    tenant_id: str


class SecurityFinding(BaseModel):
    event_id: str
    title: str
    severity: int
    confidence: float = Field(ge=0, le=1)
    evidence: dict[str, Any]
    recommended_action: str
    requires_approval: bool = True


class SecurityInvestigationResult(BaseModel):
    tenant_id: str
    target_resource: str
    security_events: list[SecurityEvent]
    iam_activities: list[dict[str, Any]]
    security_findings: list[SecurityFinding]
    affected_resources: list[str]
    timeline: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    confidence: float = Field(default=0.85, ge=0, le=1)
    hypotheses: list[dict[str, Any]]


class SecurityInvestigation(BaseModel):
    tenant_id: str
    findings: list[SecurityFinding]
    event_count: int
    highest_severity: int = Field(ge=0, le=5)
