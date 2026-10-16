"""Create FinOps cost and utilization tables.

Revision ID: 0007_finops
Revises: 0006_change_events
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_finops"
down_revision: str | None = "0006_change_events"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cost_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("account", sa.String(length=200), nullable=False),
        sa.Column("service", sa.String(length=200), nullable=False),
        sa.Column("environment", sa.String(length=100), nullable=False),
        sa.Column("amount_usd", sa.Float(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cost_records_tenant_id", "cost_records", ["tenant_id"], unique=False)
    op.create_index("ix_cost_records_service", "cost_records", ["service"], unique=False)
    op.create_table(
        "resource_utilization",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=False),
        sa.Column("service", sa.String(length=200), nullable=False),
        sa.Column("environment", sa.String(length=100), nullable=False),
        sa.Column("cpu_percent", sa.Float(), nullable=False),
        sa.Column("memory_percent", sa.Float(), nullable=False),
        sa.Column("monthly_cost_usd", sa.Float(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_resource_utilization_tenant_id", "resource_utilization", ["tenant_id"], unique=False
    )
    op.create_index(
        "ix_resource_utilization_resource_id",
        "resource_utilization",
        ["resource_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_resource_utilization_resource_id", table_name="resource_utilization")
    op.drop_index("ix_resource_utilization_tenant_id", table_name="resource_utilization")
    op.drop_table("resource_utilization")
    op.drop_index("ix_cost_records_service", table_name="cost_records")
    op.drop_index("ix_cost_records_tenant_id", table_name="cost_records")
    op.drop_table("cost_records")