"""Create LLMOps model, prompt, and evaluation tables.

Revision ID: 0009_llmops
Revises: 0008_security_events
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_llmops"
down_revision: str | None = "0008_security_events"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "models",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_models_tenant_id", "models", ["tenant_id"], unique=False)
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prompt_versions_tenant_id", "prompt_versions", ["tenant_id"], unique=False)
    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("dataset", sa.String(length=200), nullable=False),
        sa.Column("model", sa.String(length=150), nullable=False),
        sa.Column("correctness", sa.Float(), nullable=False),
        sa.Column("groundedness", sa.Float(), nullable=False),
        sa.Column("retrieval_quality", sa.Float(), nullable=False),
        sa.Column("tool_call_correctness", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evaluation_results_tenant_id", "evaluation_results", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_results_tenant_id", table_name="evaluation_results")
    op.drop_table("evaluation_results")
    op.drop_index("ix_prompt_versions_tenant_id", table_name="prompt_versions")
    op.drop_table("prompt_versions")
    op.drop_index("ix_models_tenant_id", table_name="models")
    op.drop_table("models")