from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from platform_api.database import Base


def new_id() -> str:
    return str(uuid4())


class SecretProvider(Base):
    """External or internal secret provider configuration."""

    __tablename__ = "secret_providers"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # internal_encrypted, aws_secrets_manager, azure_key_vault, gcp_secret_manager, vault
    endpoint_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vault_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    auth_method: Mapped[str] = mapped_column(
        String(100), nullable=False, default="workload_identity"
    )
    credentials_config_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="untested")
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class Secret(Base):
    """Enterprise Secret metadata record."""

    __tablename__ = "secrets"
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "environment_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    secret_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="api_key", index=True
    )  # api_key, database/cloud credential, password, oauth_secret, certificate, ssh_key, custom
    provider_id: Mapped[str] = mapped_column(
        ForeignKey("secret_providers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    scope: Mapped[str] = mapped_column(
        String(50), nullable=False, default="environment", index=True
    )  # organization, project, environment
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    environment_id: Mapped[str | None] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    modified_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="active", index=True
    )  # active, disabled, expired, revoked, pending_deletion
    expiration_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rotation_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class SecretVersion(Base):
    """Secret Version record."""

    __tablename__ = "secret_versions"
    __table_args__ = (UniqueConstraint("secret_id", "version_num"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    secret_id: Mapped[str] = mapped_column(
        ForeignKey("secrets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_num: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    provider_version_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    encrypted_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    encryption_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    comment: Mapped[str] = mapped_column(String(500), nullable=False, default="")


class SecretAssignment(Base):
    """Many-to-many assignment of a secret to authorized runtime entities."""

    __tablename__ = "secret_assignments"
    __table_args__ = (UniqueConstraint("secret_id", "entity_type", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    secret_id: Mapped[str] = mapped_column(
        ForeignKey("secrets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # agent, application, service, model_deployment, workflow, pipeline, runtime_environment
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(200), nullable=False)
    assigned_by: Mapped[str] = mapped_column(String(36), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class SecretLifecycleEvent(Base):
    __tablename__ = "secret_lifecycle_events"
    __table_args__ = (UniqueConstraint("secret_id", "event_type", "due_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    secret_id: Mapped[str] = mapped_column(
        ForeignKey("secrets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
