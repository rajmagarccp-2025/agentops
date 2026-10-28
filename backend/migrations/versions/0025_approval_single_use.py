"""Persist single-use approval consumption."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_approval_single_use"
down_revision: Union[str, None] = "0024_pgvector_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "approval_requests",
        sa.Column("consumed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "approval_requests",
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("approval_requests", "consumed_at")
    op.drop_column("approval_requests", "consumed")
