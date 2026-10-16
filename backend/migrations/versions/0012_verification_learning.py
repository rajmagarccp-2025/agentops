"""Create verification and learning tables.

Revision ID: 0012_verification_learning
Revises: 0011_remediation_actions
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_verification_learning"
down_revision: str | None = "0011_remediation_actions"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "verification_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("remediation_id", sa.String(length=36), nullable=False),
        sa.Column("recovered", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("metrics_before", sa.JSON(), nullable=False),
        sa.Column("metrics_after", sa.JSON(), nullable=False),
        sa.Column("deltas", sa.JSON(), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_verification_records_tenant_id",
        "verification_records",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_verification_records_remediation_id",
        "verification_records",
        ["remediation_id"],
        unique=False,
    )
    op.create_table(
        "learning_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("remediation_id", sa.String(length=36), nullable=False),
        sa.Column("useful", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(length=5000), nullable=False),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_learning_records_tenant_id",
        "learning_records",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_learning_records_tenant_id", table_name="learning_records")
    op.drop_table("learning_records")
    op.drop_index("ix_verification_records_remediation_id", table_name="verification_records")
    op.drop_index("ix_verification_records_tenant_id", table_name="verification_records")
    op.drop_table("verification_records")