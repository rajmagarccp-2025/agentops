"""Add document sharing table for same-organization project/environment grants.

Revision ID: 0019_rag_document_shares
Revises: 0018_cloud_integrations
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_rag_document_shares"
down_revision: str | None = "0018_cloud_integrations"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_shares",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("target_project_id", sa.String(length=36), nullable=False),
        sa.Column("target_environment_id", sa.String(length=36), nullable=True),
        sa.Column("shared_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_shares_tenant_id", "document_shares", ["tenant_id"])
    op.create_index("ix_document_shares_document_id", "document_shares", ["document_id"])
    op.create_index(
        "ix_document_shares_target_project_id", "document_shares", ["target_project_id"]
    )
    op.create_index(
        "ix_document_shares_target_environment_id",
        "document_shares",
        ["target_environment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_shares_target_environment_id", table_name="document_shares")
    op.drop_index("ix_document_shares_target_project_id", table_name="document_shares")
    op.drop_index("ix_document_shares_document_id", table_name="document_shares")
    op.drop_index("ix_document_shares_tenant_id", table_name="document_shares")
    op.drop_table("document_shares")
