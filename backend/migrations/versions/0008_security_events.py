"""Create security events table.

Revision ID: 0008_security_events
Revises: 0007_finops
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_security_events"
down_revision: str | None = "0007_finops"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "security_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("service", sa.String(length=200), nullable=True),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("actor", sa.String(length=200), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_security_events_tenant_id", "security_events", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_security_events_tenant_id", table_name="security_events")
    op.drop_table("security_events")