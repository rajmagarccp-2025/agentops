"""Add password_hash column to users table.

Revision ID: 0015_user_password_hash
Revises: 0014_auth_hierarchy_rbac
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_user_password_hash"
down_revision: str | None = "0014_auth_hierarchy_rbac"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
