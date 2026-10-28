"""Move RAG embeddings to versioned pgvector records.

Revision ID: 0024_pgvector_embeddings
Revises: 0023_workflow_outbox
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0024_pgvector_embeddings"
down_revision: str | None = "0023_workflow_outbox"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.alter_column(
        "document_chunks",
        "embedding",
        new_column_name="embedding_legacy",
    )
    op.add_column(
        "document_chunks",
        sa.Column(
            "embedding",
            Vector(768).with_variant(sa.JSON(none_as_null=True), "sqlite"),
            nullable=True,
        ),
    )
    op.add_column(
        "document_chunks",
        sa.Column(
            "embedding_provider",
            sa.String(length=50),
            nullable=False,
            server_default="hash",
        ),
    )
    op.add_column(
        "document_chunks",
        sa.Column(
            "embedding_model",
            sa.String(length=150),
            nullable=False,
            server_default="sha256-token-hash",
        ),
    )
    op.add_column(
        "document_chunks",
        sa.Column(
            "embedding_version",
            sa.String(length=50),
            nullable=False,
            server_default="hash-v1",
        ),
    )
    op.add_column(
        "document_chunks",
        sa.Column(
            "embedding_dimensions",
            sa.Integer(),
            nullable=False,
            server_default="32",
        ),
    )
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX ix_document_chunks_embedding_hnsw "
            "ON document_chunks USING hnsw (embedding vector_cosine_ops) "
            "WHERE embedding IS NOT NULL"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.drop_column("document_chunks", "embedding_dimensions")
    op.drop_column("document_chunks", "embedding_version")
    op.drop_column("document_chunks", "embedding_model")
    op.drop_column("document_chunks", "embedding_provider")
    op.drop_column("document_chunks", "embedding")
    op.alter_column(
        "document_chunks",
        "embedding_legacy",
        new_column_name="embedding",
    )
