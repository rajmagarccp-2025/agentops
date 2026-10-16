"""Add secret revocation and lifecycle event tracking.

Revision ID: 0021_secret_lifecycle_controls
Revises: 0020_durable_execution_and_audit_controls
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_secret_lifecycle_controls"
down_revision: str | None = "0020_durable_execution_and_audit_controls"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "secret_providers" not in tables:
        op.create_table(
            "secret_providers",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("tenant_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("provider_type", sa.String(length=50), nullable=False),
            sa.Column("endpoint_url", sa.String(length=500), nullable=True),
            sa.Column("vault_identifier", sa.String(length=255), nullable=True),
            sa.Column("region", sa.String(length=100), nullable=True),
            sa.Column("auth_method", sa.String(length=100), nullable=False),
            sa.Column("credentials_config_encrypted", sa.Text(), nullable=True),
            sa.Column("required_roles", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "name"),
        )
        op.create_index("ix_secret_providers_tenant_id", "secret_providers", ["tenant_id"])
        op.create_index("ix_secret_providers_provider_type", "secret_providers", ["provider_type"])

    if "secrets" not in tables:
        op.create_table(
            "secrets",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=False),
            sa.Column("secret_type", sa.String(length=50), nullable=False),
            sa.Column("provider_id", sa.String(length=36), nullable=False),
            sa.Column("scope", sa.String(length=50), nullable=False),
            sa.Column("tenant_id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=True),
            sa.Column("environment_id", sa.String(length=36), nullable=True),
            sa.Column("current_version_id", sa.String(length=36), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=False),
            sa.Column("modified_by", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("expiration_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rotation_interval_days", sa.Integer(), nullable=True),
            sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.ForeignKeyConstraint(["provider_id"], ["secret_providers.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "project_id", "environment_id", "name"),
        )
        for column in (
            "name",
            "secret_type",
            "provider_id",
            "scope",
            "tenant_id",
            "project_id",
            "environment_id",
            "status",
        ):
            op.create_index(f"ix_secrets_{column}", "secrets", [column])

    if "secret_versions" not in tables:
        op.create_table(
            "secret_versions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("secret_id", sa.String(length=36), nullable=False),
            sa.Column("version_num", sa.Integer(), nullable=False),
            sa.Column("provider_version_ref", sa.String(length=500), nullable=True),
            sa.Column("encrypted_value", sa.Text(), nullable=True),
            sa.Column("encryption_metadata", sa.JSON(), nullable=False),
            sa.Column("created_by", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("comment", sa.String(length=500), nullable=False),
            sa.ForeignKeyConstraint(["secret_id"], ["secrets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("secret_id", "version_num"),
        )
        op.create_index("ix_secret_versions_secret_id", "secret_versions", ["secret_id"])

    if "secret_assignments" not in tables:
        op.create_table(
            "secret_assignments",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("secret_id", sa.String(length=36), nullable=False),
            sa.Column("entity_type", sa.String(length=50), nullable=False),
            sa.Column("entity_id", sa.String(length=255), nullable=False),
            sa.Column("entity_name", sa.String(length=200), nullable=False),
            sa.Column("assigned_by", sa.String(length=36), nullable=False),
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["secret_id"], ["secrets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("secret_id", "entity_type", "entity_id"),
        )
        for column in ("secret_id", "entity_type", "entity_id"):
            op.create_index(f"ix_secret_assignments_{column}", "secret_assignments", [column])

    secret_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("secrets")}
    if "revoked_at" not in secret_columns:
        op.add_column("secrets", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    if "revoked_by" not in secret_columns:
        op.add_column("secrets", sa.Column("revoked_by", sa.String(length=255), nullable=True))
    op.create_table(
        "secret_lifecycle_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("secret_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["secret_id"], ["secrets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("secret_id", "event_type", "due_at"),
    )
    op.create_index(
        "ix_secret_lifecycle_events_secret_id", "secret_lifecycle_events", ["secret_id"]
    )
    op.create_index(
        "ix_secret_lifecycle_events_tenant_id", "secret_lifecycle_events", ["tenant_id"]
    )
    op.create_index(
        "ix_secret_lifecycle_events_event_type", "secret_lifecycle_events", ["event_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_secret_lifecycle_events_event_type", table_name="secret_lifecycle_events")
    op.drop_index("ix_secret_lifecycle_events_tenant_id", table_name="secret_lifecycle_events")
    op.drop_index("ix_secret_lifecycle_events_secret_id", table_name="secret_lifecycle_events")
    op.drop_table("secret_lifecycle_events")
    op.drop_column("secrets", "revoked_by")
    op.drop_column("secrets", "revoked_at")
