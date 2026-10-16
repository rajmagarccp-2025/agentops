"""Create foundational and slice operational entities.

Revision ID: 0013_foundational_and_operational_entities
Revises: 0012_verification_learning
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_foundational_entities"
down_revision: str | None = "0012_verification_learning"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # 1. Projects
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_projects_tenant_slug"),
    )
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"], unique=False)

    # 2. Environments
    op.create_table(
        "environments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "project_id", "slug", name="uq_environments_tenant_project_slug"),
    )
    op.create_index("ix_environments_tenant_id", "environments", ["tenant_id"], unique=False)
    op.create_index("ix_environments_project_id", "environments", ["project_id"], unique=False)

    # 3. Memberships
    op.create_table(
        "memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", "role_id", name="uq_memberships_tenant_user_role"),
    )
    op.create_index("ix_memberships_tenant_id", "memberships", ["tenant_id"], unique=False)
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"], unique=False)
    op.create_index("ix_memberships_role_id", "memberships", ["role_id"], unique=False)

    # 4. Services
    op.create_table(
        "services",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("environment", sa.String(length=100), nullable=False, server_default="production"),
        sa.Column("tier", sa.String(length=50), nullable=False, server_default="standard"),
        sa.Column("owner", sa.String(length=200), nullable=False, server_default="platform"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_services_tenant_id", "services", ["tenant_id"], unique=False)

    # 5. Resource Dependencies
    op.create_table(
        "dependencies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("source_resource_id", sa.String(length=255), nullable=False),
        sa.Column("target_resource_id", sa.String(length=255), nullable=False),
        sa.Column("dependency_type", sa.String(length=100), nullable=False, server_default="depends_on"),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dependencies_tenant_id", "dependencies", ["tenant_id"], unique=False)
    op.create_index("ix_dependencies_source_resource_id", "dependencies", ["source_resource_id"], unique=False)
    op.create_index("ix_dependencies_target_resource_id", "dependencies", ["target_resource_id"], unique=False)

    # 6. Incident Events
    op.create_table(
        "incident_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("incident_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_events_tenant_id", "incident_events", ["tenant_id"], unique=False)
    op.create_index("ix_incident_events_incident_id", "incident_events", ["incident_id"], unique=False)

    # 7. Incident Evidence
    op.create_table(
        "incident_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("incident_id", sa.String(length=36), nullable=False),
        sa.Column("evidence_type", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_evidence_tenant_id", "incident_evidence", ["tenant_id"], unique=False)
    op.create_index("ix_incident_evidence_incident_id", "incident_evidence", ["incident_id"], unique=False)

    # 8. Incident Hypotheses
    op.create_table(
        "incident_hypotheses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("incident_id", sa.String(length=36), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(length=50), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_hypotheses_tenant_id", "incident_hypotheses", ["tenant_id"], unique=False)
    op.create_index("ix_incident_hypotheses_incident_id", "incident_hypotheses", ["incident_id"], unique=False)

    # 9. Agent Runs
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("request_type", sa.String(length=50), nullable=False),
        sa.Column("cloud_provider", sa.String(length=50), nullable=False),
        sa.Column("environment", sa.String(length=50), nullable=False),
        sa.Column("target_resource", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="queued"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_tenant_id", "agent_runs", ["tenant_id"], unique=False)

    # 10. Agent Steps
    op.create_table(
        "agent_steps",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_steps_tenant_id", "agent_steps", ["tenant_id"], unique=False)
    op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"], unique=False)

    # 11. Checkpoint Refs
    op.create_table(
        "checkpoint_refs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("thread_id", sa.String(length=255), nullable=False),
        sa.Column("checkpoint_ns", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("checkpoint_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_checkpoint_refs_tenant_id", "checkpoint_refs", ["tenant_id"], unique=False)
    op.create_index("ix_checkpoint_refs_run_id", "checkpoint_refs", ["run_id"], unique=False)

    # 12. Tool Calls
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=150), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_calls_tenant_id", "tool_calls", ["tenant_id"], unique=False)
    op.create_index("ix_tool_calls_run_id", "tool_calls", ["run_id"], unique=False)

    # 13. LLM Requests
    op.create_table(
        "llm_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=150), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="success"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_requests_tenant_id", "llm_requests", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_llm_requests_tenant_id", table_name="llm_requests")
    op.drop_table("llm_requests")

    op.drop_index("ix_tool_calls_run_id", table_name="tool_calls")
    op.drop_index("ix_tool_calls_tenant_id", table_name="tool_calls")
    op.drop_table("tool_calls")

    op.drop_index("ix_checkpoint_refs_run_id", table_name="checkpoint_refs")
    op.drop_index("ix_checkpoint_refs_tenant_id", table_name="checkpoint_refs")
    op.drop_table("checkpoint_refs")

    op.drop_index("ix_agent_steps_run_id", table_name="agent_steps")
    op.drop_index("ix_agent_steps_tenant_id", table_name="agent_steps")
    op.drop_table("agent_steps")

    op.drop_index("ix_agent_runs_tenant_id", table_name="agent_runs")
    op.drop_table("agent_runs")

    op.drop_index("ix_incident_hypotheses_incident_id", table_name="incident_hypotheses")
    op.drop_index("ix_incident_hypotheses_tenant_id", table_name="incident_hypotheses")
    op.drop_table("incident_hypotheses")

    op.drop_index("ix_incident_evidence_incident_id", table_name="incident_evidence")
    op.drop_index("ix_incident_evidence_tenant_id", table_name="incident_evidence")
    op.drop_table("incident_evidence")

    op.drop_index("ix_incident_events_incident_id", table_name="incident_events")
    op.drop_index("ix_incident_events_tenant_id", table_name="incident_events")
    op.drop_table("incident_events")

    op.drop_index("ix_dependencies_target_resource_id", table_name="dependencies")
    op.drop_index("ix_dependencies_source_resource_id", table_name="dependencies")
    op.drop_index("ix_dependencies_tenant_id", table_name="dependencies")
    op.drop_table("dependencies")

    op.drop_index("ix_services_tenant_id", table_name="services")
    op.drop_table("services")

    op.drop_index("ix_memberships_role_id", table_name="memberships")
    op.drop_index("ix_memberships_user_id", table_name="memberships")
    op.drop_index("ix_memberships_tenant_id", table_name="memberships")
    op.drop_table("memberships")

    op.drop_index("ix_environments_project_id", table_name="environments")
    op.drop_index("ix_environments_tenant_id", table_name="environments")
    op.drop_table("environments")

    op.drop_index("ix_projects_tenant_id", table_name="projects")
    op.drop_table("projects")
