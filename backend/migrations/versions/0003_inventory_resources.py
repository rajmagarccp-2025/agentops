"""Create normalized inventory resources.

Revision ID: 0003_inventory_resources
Revises: 0002_identity_and_tenancy
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_inventory_resources"
down_revision: str | None = "0002_identity_and_tenancy"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("region", sa.String(length=100), nullable=False),
        sa.Column("environment", sa.String(length=100), nullable=False),
        sa.Column("service", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resources_tenant_id", "resources", ["tenant_id"], unique=False)
    op.create_index("ix_resources_resource_id", "resources", ["resource_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_resources_resource_id", table_name="resources")
    op.drop_index("ix_resources_tenant_id", table_name="resources")
    op.drop_table("resources")
