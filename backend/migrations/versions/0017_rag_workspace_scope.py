"""Scope RAG documents to projects and environments.

Revision ID: 0017_rag_workspace_scope
Revises: 0016_contact_messages
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_rag_workspace_scope"
down_revision: str | None = "0016_contact_messages"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("project_id", sa.String(length=36), nullable=True))
    op.add_column("documents", sa.Column("environment_id", sa.String(length=36), nullable=True))
    op.create_index("ix_documents_project_id", "documents", ["project_id"], unique=False)
    op.create_index("ix_documents_environment_id", "documents", ["environment_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_documents_environment_id", table_name="documents")
    op.drop_index("ix_documents_project_id", table_name="documents")
    op.drop_column("documents", "environment_id")
    op.drop_column("documents", "project_id")
