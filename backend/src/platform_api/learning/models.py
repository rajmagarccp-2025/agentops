from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from platform_api.database import Base


class VerificationRecordModel(Base):
    __tablename__ = "verification_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    remediation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    recovered: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    metrics_before: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    metrics_after: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    deltas: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    message: Mapped[str] = mapped_column(String(1_000), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class LearningRecordModel(Base):
    __tablename__ = "learning_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    remediation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    useful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[str] = mapped_column(String(5_000), nullable=False)
    labels: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
