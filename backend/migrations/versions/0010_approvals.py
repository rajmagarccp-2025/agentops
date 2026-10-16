"""Create approval requests table.

Revision ID: 0010_approvals
Revises: 0009_llmops
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_approvals"
down_revision: str | None = "0009_llmops"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("requester", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=200), nullable=False),
        sa.Column("tool_name", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.String(length=5000), nullable=False),
        sa.Column("risk", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("affected_resources", sa.JSON(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("approver", sa.String(length=255), nullable=True),
        sa.Column("decision_reason", sa.String(length=5000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_approval_requests_tenant_id",
        "approval_requests",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_approval_requests_tenant_id", table_name="approval_requests")
    op.drop_table("approval_requests")