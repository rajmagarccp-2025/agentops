from datetime import UTC, datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from platform_api.database import Base


class DocumentRecordModel(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    environment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    service: Mapped[str | None] = mapped_column(String(200), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    allowed_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    stale_after_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768).with_variant(JSON(none_as_null=True), "sqlite"), nullable=True
    )
    embedding_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="hash")
    embedding_model: Mapped[str] = mapped_column(String(150), nullable=False)
    embedding_version: Mapped[str] = mapped_column(String(50), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)


class DocumentShareModel(Base):
    __tablename__ = "document_shares"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_environment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    shared_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
