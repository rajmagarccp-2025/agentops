from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    RUNBOOK = "runbook"
    POSTMORTEM = "postmortem"
    POLICY = "policy"
    ARCHITECTURE = "architecture"
    TICKET = "ticket"
    CLOUD_DOCUMENTATION = "cloud_documentation"


DocumentScope = Literal["environment", "project"]


class DocumentCreate(BaseModel):
    source: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=1_000_000)
    document_type: DocumentType
    version: int = Field(default=1, ge=1)
    service: str | None = Field(default=None, max_length=200)
    environment: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=50)
    allowed_roles: list[str] = Field(default_factory=list, max_length=50)
    stale_after_days: int | None = Field(default=None, ge=1)
    scope: DocumentScope = "environment"


class DocumentRecord(BaseModel):
    id: str
    tenant_id: str
    project_id: str | None
    environment_id: str | None
    scope: Literal["environment", "project", "unassigned"]
    ingestion_status: Literal["indexed"] = "indexed"
    source: str
    title: str
    document_type: DocumentType
    version: int
    service: str | None
    environment: str | None
    tags: list[str]
    allowed_roles: list[str]
    created_at: datetime
    updated_at: datetime
    stale_after_days: int | None
    is_stale: bool = False


class DocumentChunk(BaseModel):
    id: str
    document_id: str
    tenant_id: str
    ordinal: int
    content: str
    metadata: dict[str, Any]
    embedding: list[float]


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    source: str
    version: int
    excerpt: str
    score: float
    is_stale: bool = False
    freshness_info: str = "fresh"


class RetrievalResult(BaseModel):
    query: str
    citations: list[Citation]
    context: str


class DocumentScopeUpdate(BaseModel):
    scope: DocumentScope


class DocumentShareCreate(BaseModel):
    target_project_id: str = Field(min_length=1, max_length=100)
    target_environment_id: str | None = Field(default=None, max_length=100)


class DocumentShareRecord(BaseModel):
    id: str
    document_id: str
    tenant_id: str
    target_project_id: str
    target_environment_id: str | None = None
    shared_by: str | None = None
    created_at: datetime


def utc_now() -> datetime:
    return datetime.now(UTC)
