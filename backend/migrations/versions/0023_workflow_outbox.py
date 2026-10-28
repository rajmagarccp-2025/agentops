"""Add transactional outbox for Pub/Sub workflow dispatch.

Revision ID: 0023_workflow_outbox
Revises: 0022_tool_idempotency_records
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_workflow_outbox"
down_revision: str | None = "0022_tool_idempotency_records"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_outbox",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("delivery_number", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(length=255), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["workflow_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "delivery_number"),
    )
    op.create_index("ix_workflow_outbox_job_id", "workflow_outbox", ["job_id"])
    op.create_index("ix_workflow_outbox_status", "workflow_outbox", ["status"])
    op.create_index("ix_workflow_outbox_available_at", "workflow_outbox", ["available_at"])
    op.create_index("ix_workflow_outbox_published_at", "workflow_outbox", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_workflow_outbox_published_at", table_name="workflow_outbox")
    op.drop_index("ix_workflow_outbox_available_at", table_name="workflow_outbox")
    op.drop_index("ix_workflow_outbox_status", table_name="workflow_outbox")
    op.drop_index("ix_workflow_outbox_job_id", table_name="workflow_outbox")
    op.drop_table("workflow_outbox")
