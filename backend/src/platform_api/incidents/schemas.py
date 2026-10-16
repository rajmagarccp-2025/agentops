from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class IncidentSeverity(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    service: str = Field(min_length=1, max_length=200)
    severity: IncidentSeverity
    started_at: datetime
    description: str = Field(default="", max_length=10_000)


class IncidentRecord(IncidentCreate):
    id: str
    tenant_id: str
    status: IncidentStatus = IncidentStatus.OPEN
    created_at: datetime


class TimelineEvent(BaseModel):
    timestamp: datetime
    event_type: str
    title: str
    source: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class CorrelatedIncident(BaseModel):
    incident: IncidentRecord
    timeline: list[TimelineEvent]
    evidence: list[dict[str, Any]]
    hypotheses: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_steps: list[str]
