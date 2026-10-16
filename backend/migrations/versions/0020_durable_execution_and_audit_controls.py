"""Add durable execution and append-only audit controls.

Revision ID: 0020_durable_execution_and_audit_controls
Revises: 0019_rag_document_shares
"""

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0020_durable_execution_and_audit_controls"
down_revision: str | None = "0019_rag_document_shares"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("state_json", sa.JSON(), nullable=True))
    op.add_column(
        "agent_runs",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE agent_runs SET updated_at = created_at WHERE updated_at IS NULL")
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("agent_runs", "updated_at", nullable=False)
    op.create_index("ix_agent_runs_updated_at", "agent_runs", ["updated_at"])

    op.create_table(
        "workflow_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key"),
        sa.UniqueConstraint("run_id"),
    )
    for column in ("tenant_id", "run_id", "job_type", "status", "available_at"):
        op.create_index(f"ix_workflow_jobs_{column}", "workflow_jobs", [column])
    op.create_table(
        "workflow_worker_heartbeats",
        sa.Column("worker_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("active_jobs", sa.Integer(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("worker_id"),
    )
    op.create_index(
        "ix_workflow_worker_heartbeats_last_seen_at",
        "workflow_worker_heartbeats",
        ["last_seen_at"],
    )

    op.add_column("audit_logs", sa.Column("sequence_number", sa.BigInteger(), nullable=True))
    op.add_column("audit_logs", sa.Column("previous_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("event_hash", sa.String(length=64), nullable=True))
    op.create_table(
        "audit_chain_heads",
        sa.Column("chain_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_number", sa.BigInteger(), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("chain_id"),
    )
    op.create_table(
        "audit_log_archive",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("actor_email", sa.String(length=320), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("environment_id", sa.String(length=36), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("sequence_number", sa.BigInteger(), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column("event_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_log_archive_organization_id", "audit_log_archive", ["organization_id"]
    )
    op.create_index("ix_audit_log_archive_created_at", "audit_log_archive", ["created_at"])
    _backfill_audit_chain()
    _install_append_only_guards()


def downgrade() -> None:
    _remove_append_only_guards()
    op.drop_index("ix_audit_log_archive_created_at", table_name="audit_log_archive")
    op.drop_index("ix_audit_log_archive_organization_id", table_name="audit_log_archive")
    op.drop_table("audit_log_archive")
    op.drop_table("audit_chain_heads")
    op.drop_column("audit_logs", "event_hash")
    op.drop_column("audit_logs", "previous_hash")
    op.drop_column("audit_logs", "sequence_number")
    for column in ("available_at", "status", "job_type", "run_id", "tenant_id"):
        op.drop_index(f"ix_workflow_jobs_{column}", table_name="workflow_jobs")
    op.drop_index(
        "ix_workflow_worker_heartbeats_last_seen_at",
        table_name="workflow_worker_heartbeats",
    )
    op.drop_table("workflow_worker_heartbeats")
    op.drop_table("workflow_jobs")
    op.drop_index("ix_agent_runs_updated_at", table_name="agent_runs")
    op.drop_column("agent_runs", "updated_at")
    op.drop_column("agent_runs", "state_json")


def _hash_event(event: dict[str, object], previous_hash: str) -> str:
    canonical = json.dumps(
        {"previous_hash": previous_hash, **event},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _backfill_audit_chain() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, actor, actor_email, action, resource_type, resource_id, "
            "organization_id, project_id, environment_id, details, created_at "
            "FROM audit_logs ORDER BY organization_id, created_at, id"
        )
    ).mappings()
    heads: dict[str, tuple[int, str]] = {}
    for row in rows:
        chain_id = row["organization_id"] or "__global__"
        sequence_number, previous_hash = heads.get(chain_id, (0, "0" * 64))
        sequence_number += 1
        details = row["details"]
        if isinstance(details, str):
            details = json.loads(details)
        event = {
            "actor": row["actor"],
            "actor_email": row["actor_email"],
            "action": row["action"],
            "resource_type": row["resource_type"],
            "resource_id": row["resource_id"],
            "organization_id": row["organization_id"],
            "project_id": row["project_id"],
            "environment_id": row["environment_id"],
            "details": details or {},
            "created_at": _canonical_datetime(row["created_at"]),
            "sequence_number": sequence_number,
        }
        event_hash = _hash_event(event, previous_hash)
        bind.execute(
            sa.text(
                "UPDATE audit_logs SET sequence_number=:sequence_number, "
                "previous_hash=:previous_hash, event_hash=:event_hash WHERE id=:id"
            ),
            {
                "sequence_number": sequence_number,
                "previous_hash": previous_hash,
                "event_hash": event_hash,
                "id": row["id"],
            },
        )
        heads[chain_id] = (sequence_number, event_hash)

    for chain_id, (sequence_number, event_hash) in heads.items():
        bind.execute(
            sa.text(
                "INSERT INTO audit_chain_heads (chain_id, sequence_number, event_hash) "
                "VALUES (:chain_id, :sequence_number, :event_hash)"
            ),
            {
                "chain_id": chain_id,
                "sequence_number": sequence_number,
                "event_hash": event_hash,
            },
        )


def _canonical_datetime(value: datetime | str) -> str:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.isoformat()


def _install_append_only_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION reject_audit_log_mutation() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_logs is append-only';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            "CREATE TRIGGER audit_logs_append_only BEFORE UPDATE OR DELETE ON audit_logs "
            "FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation()"
        )
        op.execute(
            "CREATE TRIGGER audit_log_archive_append_only BEFORE UPDATE OR DELETE "
            "ON audit_log_archive FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation()"
        )
    elif dialect == "sqlite":
        for table in ("audit_logs", "audit_log_archive"):
            op.execute(
                f"CREATE TRIGGER {table}_no_update BEFORE UPDATE ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'audit log tables are append-only'); END"
            )
            op.execute(
                f"CREATE TRIGGER {table}_no_delete BEFORE DELETE ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'audit log tables are append-only'); END"
            )


def _remove_append_only_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER audit_log_archive_append_only ON audit_log_archive")
        op.execute("DROP TRIGGER audit_logs_append_only ON audit_logs")
        op.execute("DROP FUNCTION reject_audit_log_mutation()")
    elif dialect == "sqlite":
        for table in ("audit_logs", "audit_log_archive"):
            op.execute(f"DROP TRIGGER {table}_no_update")
            op.execute(f"DROP TRIGGER {table}_no_delete")
