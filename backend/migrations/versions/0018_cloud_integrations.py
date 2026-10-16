"""Add workspace-scoped cloud integration reference records.

Revision ID: 0018_cloud_integrations
Revises: 0017_rag_workspace_scope
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_cloud_integrations"
down_revision: str | None = "0017_rag_workspace_scope"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cloud_integrations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("environment_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("account_id", sa.String(length=200), nullable=False),
        sa.Column("identity_reference", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="unverified"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "project_id", "environment_id", "provider", "account_id"
        ),
    )
    op.create_index("ix_cloud_integrations_tenant_id", "cloud_integrations", ["tenant_id"])
    op.create_index("ix_cloud_integrations_project_id", "cloud_integrations", ["project_id"])
    op.create_index("ix_cloud_integrations_environment_id", "cloud_integrations", ["environment_id"])


def downgrade() -> None:
    op.drop_index("ix_cloud_integrations_environment_id", table_name="cloud_integrations")
    op.drop_index("ix_cloud_integrations_project_id", table_name="cloud_integrations")
    op.drop_index("ix_cloud_integrations_tenant_id", table_name="cloud_integrations")
    op.drop_table("cloud_integrations")
