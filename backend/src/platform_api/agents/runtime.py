from collections.abc import Iterator
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi.encoders import jsonable_encoder
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from platform_api.agents.models import AgentRunRecord, AgentStepRecord
from platform_api.agents.nodes import (
    change_node,
    discovery_node,
    finops_node,
    governance_node,
    investigation_node,
    llmops_node,
    mlops_node,
    remediation_node,
    security_node,
    sre_node,
    supervisor_node,
)
from platform_api.agents.state import AgentRoute, AgentState
from platform_api.database import SessionLocal, engine
from platform_api.mcp.gateway import tool_registry
from platform_api.observability import increment, span
from platform_api.security import Principal
from platform_api.workflow_queue import WorkflowJobRecord, WorkflowJobStatus, workflow_queue


class AgentRuntime:
    _checkpointer_context: AbstractContextManager[BaseCheckpointSaver[Any]] | None

    def _create_checkpointer(self) -> BaseCheckpointSaver[Any]:
        if engine.dialect.name == "postgresql":
            connection_string = engine.url.render_as_string(hide_password=False)
            connection_string = connection_string.replace(
                "postgresql+psycopg://", "postgresql://", 1
            )
            postgres_context = PostgresSaver.from_conn_string(connection_string)
            self._checkpointer_context = cast(
                AbstractContextManager[BaseCheckpointSaver[Any]],
                postgres_context,
            )
            postgres_checkpointer = postgres_context.__enter__()
            postgres_checkpointer.setup()
            return postgres_checkpointer

        database_path = engine.url.database or ":memory:"
        sqlite_context = SqliteSaver.from_conn_string(database_path)
        self._checkpointer_context = cast(
            AbstractContextManager[BaseCheckpointSaver[Any]],
            sqlite_context,
        )
        sqlite_checkpointer = sqlite_context.__enter__()
        sqlite_checkpointer.setup()
        return sqlite_checkpointer

    def _persist_run_state(self, state: AgentState) -> None:
        with SessionLocal() as db:
            run = db.get(AgentRunRecord, state["run_id"])
            if run is None:
                run = AgentRunRecord(
                    id=state["run_id"],
                    tenant_id=state.get("tenant_id", "unknown"),
                    subject=state.get("subject", "system"),
                    request=state.get("request", ""),
                    request_type=state.get("request_type", "sre"),
                    cloud_provider=state.get("cloud_provider", "aws"),
                    environment=state.get("environment", "production"),
                    target_resource=state.get("target_resource", "unknown"),
                )
                db.add(run)
            run.tenant_id = state.get("tenant_id", run.tenant_id)
            run.subject = state.get("subject", run.subject)
            run.request = state.get("request", run.request)
            run.request_type = state.get("request_type", run.request_type)
            run.cloud_provider = state.get("cloud_provider", run.cloud_provider)
            run.environment = state.get("environment", run.environment)
            run.target_resource = state.get("target_resource", run.target_resource)
            run.status = state.get("status", run.status)
            run.state_json = jsonable_encoder(dict(state))
            run.updated_at = datetime.now(UTC)
            if state.get("status") in {"completed", "failed", "cancelled"}:
                run.completed_at = datetime.now(UTC)
            else:
                run.completed_at = None

            for index, step in enumerate(state.get("steps", []), start=1):
                step_id = str(uuid5(NAMESPACE_URL, f"agent-step:{state['run_id']}:{index}"))
                record = db.get(AgentStepRecord, step_id)
                if record is None:
                    record = AgentStepRecord(
                        id=step_id,
                        tenant_id=state.get("tenant_id", "unknown"),
                        run_id=state["run_id"],
                        step_number=index,
                        agent_name=str(step.get("agent", "runtime")),
                        action=str(step.get("status", "step")),
                        status=str(step.get("status", "unknown")),
                        output=jsonable_encoder(dict(step)),
                    )
                    db.add(record)
                else:
                    record.agent_name = str(step.get("agent", "runtime"))
                    record.action = str(step.get("status", "step"))
                    record.status = str(step.get("status", "unknown"))
                    record.output = jsonable_encoder(dict(step))
            db.commit()

    def __init__(self) -> None:
        self._checkpointer_context = None
        self.checkpointer = self._create_checkpointer()
        builder = StateGraph(AgentState)
        builder.add_node("supervisor", supervisor_node)
        builder.add_node("discovery", discovery_node)
        builder.add_node("sre", sre_node)
        builder.add_node("investigation", investigation_node)
        builder.add_node("change", change_node)
        builder.add_node("finops", finops_node)
        builder.add_node("security", security_node)
        builder.add_node("mlops", mlops_node)
        builder.add_node("llmops", llmops_node)
        builder.add_node("remediation", remediation_node)
        builder.add_node("governance", governance_node)

        builder.add_edge(START, "supervisor")
        builder.add_conditional_edges(
            "supervisor",
            lambda state: state["next_agent"],
            {
                "discovery": "discovery",
                "sre": "sre",
                "investigation": "investigation",
                "change": "change",
                "finops": "finops",
                "security": "security",
                "mlops": "mlops",
                "llmops": "llmops",
                "remediation": "remediation",
                "governance": "governance",
            },
        )
        builder.add_edge("discovery", END)
        builder.add_edge("sre", END)
        builder.add_edge("investigation", END)
        builder.add_edge("change", END)
        builder.add_edge("finops", END)
        builder.add_edge("governance", END)
        builder.add_edge("security", END)
        builder.add_edge("mlops", END)
        builder.add_edge("llmops", END)
        builder.add_edge("remediation", END)

        self.graph = builder.compile(checkpointer=self.checkpointer)

    def enqueue(
        self,
        *,
        request: str,
        request_type: AgentRoute,
        tenant_id: str,
        subject: str,
        permissions: list[str],
        cloud_provider: str = "aws",
        environment: str = "production",
        account_id: str = "demo-account",
        region: str = "us-east-1",
        target_resource: str = "checkout-api",
        namespace: str = "default",
        cluster: str = "gke-prod-01",
        project_id: str = "proj-sre-01",
        workspace_project_id: str | None = None,
        workspace_environment_id: str | None = None,
        deployment: str = "checkout-api",
        initial_evidence: list[dict[str, object]] | None = None,
        idempotency_key: str | None = None,
    ) -> AgentState:
        run_id = str(uuid4())
        payload: dict[str, Any] = {
            "request": request,
            "request_type": request_type,
            "tenant_id": tenant_id,
            "subject": subject,
            "permissions": permissions,
            "cloud_provider": cloud_provider,
            "environment": environment,
            "account_id": account_id,
            "region": region,
            "target_resource": target_resource,
            "namespace": namespace,
            "cluster": cluster,
            "project_id": project_id,
            "workspace_project_id": workspace_project_id,
            "workspace_environment_id": workspace_environment_id,
            "deployment": deployment,
            "initial_evidence": initial_evidence or [],
            "run_id": run_id,
        }
        retry_safe = request_type != "remediation"
        job = workflow_queue.enqueue(
            tenant_id=tenant_id,
            job_type="agent_run",
            payload={**payload, "retry_safe": retry_safe},
            run_id=run_id,
            idempotency_key=idempotency_key,
        )
        if job.run_id != run_id:
            if job.run_id is None:
                raise RuntimeError("Idempotent agent job does not have a run ID")
            return self.get(job.run_id)
        correlation_id = str(uuid4())
        return cast(AgentState, {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "subject": subject,
            "permissions": permissions,
            "request": request,
            "request_type": request_type,
            "cloud_provider": cloud_provider,
            "environment": environment,
            "account_id": account_id,
            "region": region,
            "target_resource": target_resource,
            "namespace": namespace,
            "cluster": cluster,
            "project_id": project_id,
            "workspace_project_id": workspace_project_id or "",
            "workspace_environment_id": workspace_environment_id or "",
            "deployment": deployment,
            "status": job.status,
            "correlation_id": correlation_id,
            "trace_id": correlation_id,
            "steps": [],
            "evidence": initial_evidence or [],
            "retry_count": 0,
            "max_retries": job.max_attempts,
        })

    def run(
        self,
        *,
        request: str,
        request_type: AgentRoute,
        tenant_id: str,
        subject: str,
        permissions: list[str],
        cloud_provider: str = "aws",
        environment: str = "production",
        account_id: str = "demo-account",
        region: str = "us-east-1",
        target_resource: str = "checkout-api",
        namespace: str = "default",
        cluster: str = "gke-prod-01",
        project_id: str = "proj-sre-01",
        workspace_project_id: str | None = None,
        workspace_environment_id: str | None = None,
        deployment: str = "checkout-api",
        initial_evidence: list[dict[str, object]] | None = None,
        run_id: str | None = None,
    ) -> AgentState:
        execution_id = run_id or str(uuid4())
        correlation_id = str(uuid4())
        initial: AgentState = {
            "run_id": execution_id,
            "tenant_id": tenant_id,
            "subject": subject,
            "permissions": permissions,
            "request": request,
            "request_type": request_type,
            "cloud_provider": cloud_provider,
            "environment": environment,
            "account_id": account_id,
            "region": region,
            "target_resource": target_resource,
            "namespace": namespace,
            "cluster": cluster,
            "project_id": project_id,
            "workspace_project_id": workspace_project_id or "",
            "workspace_environment_id": workspace_environment_id or "",
            "deployment": deployment,
            "status": "queued",
            "correlation_id": correlation_id,
            "trace_id": correlation_id,
            "steps": [],
            "evidence": initial_evidence or [],
            "retry_count": 0,
            "max_retries": 3,
        }
        initial["status"] = "running"
        config: RunnableConfig = {"configurable": {"thread_id": execution_id}}
        checkpoint = self.graph.get_state(config)
        has_checkpoint = bool(checkpoint.values)
        if not has_checkpoint:
            self._persist_run_state(initial)
        from time import perf_counter

        from platform_api.observability import record_workflow_metrics

        wf_start = perf_counter()
        span_attrs: dict[str, object] = {
            "request_id": correlation_id,
            "correlation_id": correlation_id,
            "trace_id": correlation_id,
            "tenant_id": tenant_id,
            "user_id": subject,
            "workflow_id": f"wf-{request_type}",
            "agent_run_id": execution_id,
            "agent_id": request_type,
            "service_id": target_resource,
        }
        with span("agent.workflow", span_attrs):
            try:
                if has_checkpoint and not checkpoint.next:
                    result = checkpoint.values
                else:
                    result = self.graph.invoke(None if has_checkpoint else initial, config)
            except Exception as exc:
                # Handle failure gracefully with FAILED state & bounded retry recording
                error_state: AgentState = {
                    **initial,
                    "status": "failed",
                    "error": str(exc),
                    "steps": [
                        {"agent": "runtime", "status": "failed", "error": str(exc)},
                    ],
                }
                self.graph.update_state(config, error_state)
                self._persist_run_state(error_state)
                increment("agent.runs.failed")
                record_workflow_metrics(
                    f"wf-{request_type}", "failed", (perf_counter() - wf_start) * 1000
                )
                return error_state

        final_state = cast(AgentState, result)
        # Standardize state mapping
        if final_state.get("status") == "started" or final_state.get("status") == "running":
            final_state["status"] = "completed"
        self._persist_run_state(final_state)
        increment("agent.runs.total")
        record_workflow_metrics(
            f"wf-{request_type}",
            final_state.get("status", "completed"),
            (perf_counter() - wf_start) * 1000,
        )
        return final_state

    def stream(
        self,
        *,
        request: str,
        request_type: AgentRoute,
        tenant_id: str,
        subject: str,
        permissions: list[str],
        cloud_provider: str = "aws",
        environment: str = "production",
        account_id: str = "demo-account",
        region: str = "us-east-1",
        target_resource: str = "checkout-api",
        namespace: str = "default",
        cluster: str = "gke-prod-01",
        project_id: str = "proj-sre-01",
        workspace_project_id: str | None = None,
        workspace_environment_id: str | None = None,
        deployment: str = "checkout-api",
        initial_evidence: list[dict[str, object]] | None = None,
        run_id: str | None = None,
    ) -> Iterator[dict[str, object]]:
        execution_id = run_id or str(uuid4())
        correlation_id = str(uuid4())
        initial: AgentState = {
            "run_id": execution_id,
            "tenant_id": tenant_id,
            "subject": subject,
            "permissions": permissions,
            "request": request,
            "request_type": request_type,
            "cloud_provider": cloud_provider,
            "environment": environment,
            "account_id": account_id,
            "region": region,
            "target_resource": target_resource,
            "namespace": namespace,
            "cluster": cluster,
            "project_id": project_id,
            "workspace_project_id": workspace_project_id or "",
            "workspace_environment_id": workspace_environment_id or "",
            "deployment": deployment,
            "status": "queued",
            "correlation_id": correlation_id,
            "trace_id": correlation_id,
            "steps": [],
            "evidence": initial_evidence or [],
            "retry_count": 0,
            "max_retries": 3,
        }

        yield {
            "event": "start",
            "run_id": execution_id,
            "node": "supervisor",
            "status": "started",
            "request_type": request_type,
            "target_resource": target_resource,
            "environment": environment,
        }

        try:
            for step_event in self.graph.stream(
                initial,
                {"configurable": {"thread_id": execution_id}},
                stream_mode="updates",
            ):
                for node_name, node_update in step_event.items():
                    yield {
                        "event": "node_update",
                        "run_id": execution_id,
                        "node": node_name,
                        "status": node_update.get("status", "running"),
                        "steps": node_update.get("steps", []),
                        "structured_findings": node_update.get("structured_findings", []),
                        "hypotheses": node_update.get("hypotheses", []),
                        "confidence": node_update.get("confidence"),
                        "recommendation": node_update.get("recommendation"),
                        "approval_required": node_update.get("approval_required", False),
                        "approval_id": node_update.get("approval_id"),
                    }
        except Exception as exc:
            yield {
                "event": "error",
                "run_id": execution_id,
                "node": "runtime",
                "status": "failed",
                "error": str(exc),
            }
            return

        final_state = self.get(execution_id)
        yield {
            "event": "complete",
            "run_id": execution_id,
            "node": "end",
            "status": final_state.get("status", "completed"),
            "recommendation": final_state.get("recommendation"),
            "structured_findings": final_state.get("structured_findings", []),
            "evidence": final_state.get("evidence", []),
            "steps": final_state.get("steps", []),
        }

    def get(self, run_id: str) -> AgentState:
        snapshot = self.graph.get_state({"configurable": {"thread_id": run_id}})
        if snapshot.values:
            return cast(AgentState, snapshot.values)
        with SessionLocal() as db:
            record = db.get(AgentRunRecord, run_id)
            job = db.scalar(
                select(WorkflowJobRecord).where(WorkflowJobRecord.run_id == run_id)
            )
            if record is not None and record.state_json is not None:
                state = cast(AgentState, record.state_json)
                if job is not None and job.status in {
                    WorkflowJobStatus.CANCELLED,
                    WorkflowJobStatus.DEAD_LETTER,
                }:
                    terminal_status: Literal["cancelled", "failed"] = (
                        "cancelled"
                        if job.status == WorkflowJobStatus.CANCELLED
                        else "failed"
                    )
                    state = {
                        **state,
                        "status": terminal_status,
                    }
                    if job.error_message is not None:
                        state["error"] = job.error_message
                return state
            if job is not None:
                payload = {key: value for key, value in job.payload.items() if key != "retry_safe"}
                return cast(
                    AgentState,
                    {
                        **payload,
                        "run_id": run_id,
                        "status": job.status,
                        "correlation_id": run_id,
                        "trace_id": run_id,
                        "steps": [],
                        "evidence": payload.get("initial_evidence", []),
                        "retry_count": max(job.attempts - 1, 0),
                        "max_retries": job.max_attempts,
                    },
                )
        raise KeyError(run_id)

    def list_recent(self, tenant_id: str, limit: int = 20) -> list[tuple[AgentState, str]]:
        with SessionLocal() as db:
            records = db.scalars(
                select(AgentRunRecord)
                .where(AgentRunRecord.tenant_id == tenant_id)
                .order_by(AgentRunRecord.updated_at.desc())
                .limit(limit)
            ).all()
            recent = [
                (cast(AgentState, record.state_json), record.updated_at.isoformat())
                for record in records
                if record.state_json is not None
            ]
            known_run_ids = {state["run_id"] for state, _ in recent}
            jobs = db.scalars(
                select(WorkflowJobRecord)
                .where(
                    WorkflowJobRecord.tenant_id == tenant_id,
                    WorkflowJobRecord.run_id.is_not(None),
                )
                .order_by(WorkflowJobRecord.updated_at.desc())
                .limit(limit)
            ).all()
            for job in jobs:
                if job.run_id is None:
                    continue
                if job.run_id not in known_run_ids:
                    recent.append((self.get(job.run_id), job.updated_at.isoformat()))
                    known_run_ids.add(job.run_id)
                elif job.status in {
                    WorkflowJobStatus.CANCELLED,
                    WorkflowJobStatus.DEAD_LETTER,
                }:
                    state = self.get(job.run_id)
                    recent = [
                        (state, job.updated_at.isoformat())
                        if existing["run_id"] == job.run_id
                        else (existing, updated_at)
                        for existing, updated_at in recent
                    ]
            return sorted(recent, key=lambda item: item[1], reverse=True)[:limit]

    def cancel(
        self,
        run_id: str,
        reason: str = "User cancelled workflow",
        tenant_id: str | None = None,
    ) -> AgentState:
        with SessionLocal() as db:
            run_record = db.get(AgentRunRecord, run_id)
            job = db.scalar(
                select(WorkflowJobRecord).where(WorkflowJobRecord.run_id == run_id)
            )
            resolved_tenant = tenant_id or (run_record.tenant_id if run_record else None)
            if resolved_tenant is None and job is not None:
                resolved_tenant = job.tenant_id
            if tenant_id is not None and (
                (run_record is not None and run_record.tenant_id != tenant_id)
                or (job is not None and job.tenant_id != tenant_id)
            ):
                raise KeyError(run_id)
            state = (
                cast(AgentState, run_record.state_json)
                if run_record is not None and run_record.state_json is not None
                else None
            )
        if state is None:
            try:
                state = self.get(run_id)
            except KeyError:
                state = None
        if state is None and job is None:
            raise KeyError(run_id)
        if state is not None and state.get("status") in {"completed", "failed"}:
            raise ValueError(f"Cannot cancel an agent run with status '{state['status']}'.")
        if state is not None and state.get("status") == "cancelled":
            return state
        if resolved_tenant is not None:
            workflow_queue.cancel_run(run_id, tenant_id=resolved_tenant, reason=reason)
        if state is None and job is not None:
            payload = {key: value for key, value in job.payload.items() if key != "retry_safe"}
            correlation_id = run_id
            state = cast(
                AgentState,
                {
                    **payload,
                    "status": "pending",
                    "correlation_id": correlation_id,
                    "trace_id": correlation_id,
                    "steps": [],
                    "evidence": payload.get("initial_evidence", []),
                    "retry_count": max(job.attempts - 1, 0),
                    "max_retries": job.max_attempts,
                },
            )
        if state is None:
            raise RuntimeError(f"Agent run {run_id} has no persisted state")
        cancelled_state: AgentState = {
            **state,
            "status": "cancelled",
            "error": reason,
            "steps": [
                *state.get("steps", []),
                {"agent": "runtime", "status": "cancelled", "reason": reason},
            ],
        }
        if self.checkpointer.get_tuple({"configurable": {"thread_id": run_id}}) is not None:
            self.graph.update_state({"configurable": {"thread_id": run_id}}, cancelled_state)
        self._persist_run_state(cancelled_state)
        return cancelled_state

    def resume_approved_remediation(
        self,
        run_id: str,
        approver: str,
    ) -> AgentState:
        state = self.get(run_id)
        if state.get("status") not in ("paused", "awaiting_approval") or not state.get(
            "approval_required"
        ):
            raise ValueError("Agent run is not awaiting approval")
        principal = Principal(
            subject=approver,
            tenant_id=state["tenant_id"],
            roles=frozenset(),
            permissions=frozenset({"tools:execute"}),
        )
        execution = tool_registry.execute(
            "kubernetes.scale_deployment",
            {
                "namespace": state.get("environment", "production"),
                "deployment": state.get("target_resource", "checkout-api"),
                "replicas": 4,
            },
            principal,
            run_id,
            False,
            approved=True,
        )
        config: RunnableConfig = {"configurable": {"thread_id": run_id}}
        self.graph.update_state(
            config,
            {
                "status": "completed" if execution.status == "executed" else execution.status,
                "approval_required": False,
                "steps": [
                    *state.get("steps", []),
                    {"agent": "approval", "approver": approver, "status": execution.status},
                ],
            },
        )
        final_state = cast(AgentState, self.graph.get_state(config).values)
        self._persist_run_state(final_state)
        return final_state


agent_runtime = AgentRuntime()
