"""Persist MCP tool idempotency reservations and results.

Revision ID: 0022_tool_idempotency_records
Revises: 0021_secret_lifecycle_controls
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_tool_idempotency_records"
down_revision: str | None = "0021_secret_lifecycle_controls"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tool_idempotency_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=150), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("execution_id", sa.String(length=36), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "tool_name", "idempotency_key"),
    )
    op.create_index(
        "ix_tool_idempotency_records_tenant_id", "tool_idempotency_records", ["tenant_id"]
    )
    op.create_index(
        "ix_tool_idempotency_records_status", "tool_idempotency_records", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_tool_idempotency_records_status", table_name="tool_idempotency_records")
    op.drop_index(
        "ix_tool_idempotency_records_tenant_id", table_name="tool_idempotency_records"
    )
    op.drop_table("tool_idempotency_records")
