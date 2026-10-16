"""Create change events table.

Revision ID: 0006_change_events
Revises: 0005_rag_documents
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_change_events"
down_revision: str | None = "0005_rag_documents"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "change_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("service", sa.String(length=200), nullable=False),
        sa.Column("environment", sa.String(length=100), nullable=False),
        sa.Column("change_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("actor", sa.String(length=200), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_change_events_tenant_id", "change_events", ["tenant_id"], unique=False)
    op.create_index("ix_change_events_service", "change_events", ["service"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_change_events_service", table_name="change_events")
    op.drop_index("ix_change_events_tenant_id", table_name="change_events")
    op.drop_table("change_events")