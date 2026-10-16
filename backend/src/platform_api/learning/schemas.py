from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class VerificationResult(BaseModel):
    id: str
    tenant_id: str
    remediation_id: str
    recovered: bool
    confidence: float = Field(ge=0, le=1)
    metrics_before: dict[str, float]
    metrics_after: dict[str, float]
    deltas: dict[str, float]
    message: str
    verified_at: datetime


class LearningFeedbackCreate(BaseModel):
    remediation_id: str
    useful: bool
    notes: str = Field(default="", max_length=5_000)
    labels: list[str] = Field(default_factory=list)


class LearningRecord(LearningFeedbackCreate):
    id: str
    tenant_id: str
    created_at: datetime


def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(UTC)
