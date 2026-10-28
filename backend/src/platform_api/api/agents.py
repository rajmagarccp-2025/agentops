import asyncio
import time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from platform_api.agents.service import agent_runtime
from platform_api.agents.state import AgentState, HypothesisItem, StructuredFinding
from platform_api.config import get_settings
from platform_api.security import Principal, get_current_principal, require_permission
from platform_api.workflow_queue import WorkflowQueueFullError, workflow_queue

router = APIRouter(prefix="/agent-runs", tags=["agents"])
AgentRunType = Literal[
    "discovery",
    "sre",
    "investigation",
    "change",
    "finops",
    "security",
    "mlops",
    "llmops",
    "remediation",
    "governance",
]


class AgentRunRequest(BaseModel):
    request: str = Field(min_length=1, max_length=20_000)
    request_type: AgentRunType = "sre"
    cloud_provider: str = Field(default="gcp", max_length=50)
    environment: str = Field(default="production", max_length=50)
    account_id: str = Field(default="demo-account", max_length=100)
    region: str = Field(default="us-central1", max_length=50)
    target_resource: str = Field(default="checkout-api-pod-1", max_length=200)
    namespace: str = Field(default="default", max_length=100)
    cluster: str = Field(default="gke-prod-01", max_length=100)
    project_id: str = Field(default="proj-sre-01", max_length=100)
    deployment: str = Field(default="checkout-api", max_length=100)


class AgentRunResponse(BaseModel):
    run_id: str
    status: str
    request_type: AgentRunType
    cloud_provider: str | None = None
    environment: str | None = None
    account_id: str | None = None
    region: str | None = None
    target_resource: str | None = None
    namespace: str | None = None
    cluster: str | None = None
    project_id: str | None = None
    workspace_project_id: str | None = None
    workspace_environment_id: str | None = None
    deployment: str | None = None
    approval_required: bool = False
    approval_id: str | None = None
    inventory_count: int | None = None
    structured_findings: list[StructuredFinding] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    hypotheses: list[HypothesisItem] = Field(default_factory=list)
    confidence: float | None = None
    missing_evidence: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    recommendations: list[str] = Field(default_factory=list)
    evidence: list[dict[str, object]] = Field(default_factory=list)
    steps: list[dict[str, object]] = Field(default_factory=list)
    error: str | None = None


class AgentRunListItem(BaseModel):
    run_id: str
    status: str
    request_type: AgentRunType
    project_id: str | None = None
    workspace_project_id: str | None = None
    workspace_environment_id: str | None = None
    environment: str | None = None
    target_resource: str | None = None
    error: str | None = None
    updated_at: str


class AgentRunReplayResponse(BaseModel):
    run_id: str
    job_id: str
    status: str
    attempts: int


def get_agent_run_reader(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Principal:
    read_permissions = {"agents:read", "agents.read", "agents:run", "agents.run"}
    if not principal.permissions.intersection(read_permissions):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Cannot view agent runs",
        )
    return principal


def _response(state: AgentState) -> AgentRunResponse:
    return AgentRunResponse(
        run_id=state["run_id"],
        status=state.get("status", "unknown"),
        request_type=state.get("request_type", "sre"),
        cloud_provider=state.get("cloud_provider"),
        environment=state.get("environment"),
        account_id=state.get("account_id"),
        region=state.get("region"),
        target_resource=state.get("target_resource"),
        namespace=state.get("namespace"),
        cluster=state.get("cluster"),
        project_id=state.get("project_id"),
        workspace_project_id=state.get("workspace_project_id") or None,
        workspace_environment_id=state.get("workspace_environment_id") or None,
        deployment=state.get("deployment"),
        approval_required=state.get("approval_required", False),
        approval_id=state.get("approval_id"),
        inventory_count=state.get("inventory_count"),
        structured_findings=state.get("structured_findings", []),
        findings=state.get("findings", []),
        hypotheses=state.get("hypotheses", []),
        confidence=state.get("confidence"),
        missing_evidence=state.get("missing_evidence", []),
        recommendation=state.get("recommendation"),
        recommendations=state.get("recommendations", []),
        evidence=state.get("evidence", []),
        steps=state.get("steps", []),
        error=state.get("error"),
    )


@router.get("", response_model=list[AgentRunListItem])
async def list_agent_runs(
    principal: Annotated[Principal, Depends(require_permission("agents:read"))],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[AgentRunListItem]:
    return [
        AgentRunListItem(
            run_id=state["run_id"],
            status=state.get("status", "unknown"),
            request_type=state.get("request_type", "sre"),
            project_id=state.get("project_id"),
            workspace_project_id=state.get("workspace_project_id") or None,
            workspace_environment_id=state.get("workspace_environment_id") or None,
            environment=state.get("environment"),
            target_resource=state.get("target_resource"),
            error=state.get("error"),
            updated_at=updated_at,
        )
        for state, updated_at in agent_runtime.list_recent(principal.tenant_id, limit)
        if (
            (not principal.project_id or state.get("workspace_project_id") == principal.project_id)
            and (
                not principal.environment_id
                or state.get("workspace_environment_id") == principal.environment_id
            )
        )
    ]


@router.post("", response_model=AgentRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_agent_run(
    body: AgentRunRequest,
    principal: Annotated[Principal, Depends(require_permission("agents:run"))],
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AgentRunResponse:
    try:
        state = agent_runtime.enqueue(
            request=body.request,
            request_type=body.request_type,
            tenant_id=principal.tenant_id,
            subject=principal.subject,
            permissions=list(principal.permissions),
            cloud_provider=body.cloud_provider,
            environment=body.environment,
            account_id=body.account_id,
            region=body.region,
            target_resource=body.target_resource,
            namespace=body.namespace,
            cluster=body.cluster,
            project_id=body.project_id,
            workspace_project_id=principal.project_id,
            workspace_environment_id=principal.environment_id,
            deployment=body.deployment,
            idempotency_key=idempotency_key,
        )
    except WorkflowQueueFullError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Workflow queue is at capacity; retry later.",
            headers={"Retry-After": "10"},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    response.status_code = status.HTTP_202_ACCEPTED
    return _response(state)


@router.get("/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(
    run_id: str,
    principal: Annotated[Principal, Depends(get_agent_run_reader)],
) -> AgentRunResponse:
    try:
        state = agent_runtime.get(run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found",
        ) from exc
    if (
        state.get("tenant_id") != principal.tenant_id
        or (principal.project_id and state.get("workspace_project_id") != principal.project_id)
        or (
            principal.environment_id
            and state.get("workspace_environment_id") != principal.environment_id
        )
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    return _response(state)


@router.post("/{run_id}/cancel", response_model=AgentRunResponse)
async def cancel_agent_run(
    run_id: str,
    principal: Annotated[Principal, Depends(get_agent_run_reader)],
) -> AgentRunResponse:
    try:
        state = agent_runtime.get(run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found",
        ) from exc
    if (
        state.get("tenant_id") != principal.tenant_id
        or (principal.project_id and state.get("workspace_project_id") != principal.project_id)
        or (
            principal.environment_id
            and state.get("workspace_environment_id") != principal.environment_id
        )
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    try:
        return _response(agent_runtime.cancel(run_id, tenant_id=principal.tenant_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found",
        ) from exc


@router.post(
    "/{run_id}/replay",
    response_model=AgentRunReplayResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def replay_dead_letter_agent_run(
    run_id: str,
    principal: Annotated[Principal, Depends(require_permission("workflow:replay"))],
) -> AgentRunReplayResponse:
    try:
        state = agent_runtime.get(run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found",
        ) from exc
    if (
        state.get("tenant_id") != principal.tenant_id
        or (principal.project_id and state.get("workspace_project_id") != principal.project_id)
        or (
            principal.environment_id
            and state.get("workspace_environment_id") != principal.environment_id
        )
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    try:
        job = workflow_queue.replay_dead_letter(
            run_id,
            tenant_id=principal.tenant_id,
            actor=principal.subject,
            actor_email=principal.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    return AgentRunReplayResponse(
        run_id=run_id,
        job_id=job.id,
        status=job.status,
        attempts=job.attempts,
    )


@router.post("/stream")
async def stream_agent_run(
    body: AgentRunRequest,
    principal: Annotated[Principal, Depends(require_permission("agents:run"))],
):
    """Stream durable workflow state changes over Server-Sent Events."""
    import json

    from fastapi.responses import StreamingResponse

    try:
        initial = agent_runtime.enqueue(
            request=body.request,
            request_type=body.request_type,
            tenant_id=principal.tenant_id,
            subject=principal.subject,
            permissions=list(principal.permissions),
            cloud_provider=body.cloud_provider,
            environment=body.environment,
            account_id=body.account_id,
            region=body.region,
            target_resource=body.target_resource,
            namespace=body.namespace,
            cluster=body.cluster,
            project_id=body.project_id,
            workspace_project_id=principal.project_id,
            workspace_environment_id=principal.environment_id,
            deployment=body.deployment,
        )
    except WorkflowQueueFullError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Workflow queue is at capacity; retry later.",
            headers={"Retry-After": "10"},
        ) from exc

    async def event_generator():
        start_event = {"event": "start", "run_id": initial["run_id"], "status": "queued"}
        yield f"data: {json.dumps(start_event)}\n\n"
        last_state: tuple[str, int] | None = None
        deadline = time.monotonic() + get_settings().workflow_job_timeout_seconds + 30
        while time.monotonic() < deadline:
            try:
                current = await asyncio.to_thread(agent_runtime.get, initial["run_id"])
            except KeyError:
                unavailable = {
                    "event": "error",
                    "run_id": initial["run_id"],
                    "error": "Workflow run state is unavailable",
                }
                yield f"data: {json.dumps(unavailable)}\n\n"
                return
            steps = current.get("steps", [])
            state_key = (str(current.get("status", "unknown")), len(steps))
            if state_key != last_state:
                last_state = state_key
                if steps:
                    for step in steps:
                        yield (
                            "data: "
                            + json.dumps(
                                {
                                    "event": "node_update",
                                    "run_id": initial["run_id"],
                                    "node": step.get("agent", "runtime"),
                                    "status": step.get("status", current.get("status")),
                                    "recommendation": current.get("recommendation"),
                                    "structured_findings": current.get("structured_findings", []),
                                    "hypotheses": current.get("hypotheses", []),
                                    "confidence": current.get("confidence"),
                                },
                                default=str,
                            )
                            + "\n\n"
                        )
                if current.get("status") in {"completed", "paused"}:
                    yield (
                        "data: "
                        + json.dumps(
                            {
                                "event": "complete",
                                "run_id": initial["run_id"],
                                "status": current.get("status"),
                                "recommendation": current.get("recommendation"),
                                "structured_findings": current.get("structured_findings", []),
                                "evidence": current.get("evidence", []),
                                "steps": steps,
                            },
                            default=str,
                        )
                        + "\n\n"
                    )
                    return
                if current.get("status") in {"failed", "cancelled"}:
                    yield (
                        "data: "
                        + json.dumps(
                            {
                                "event": "error",
                                "run_id": initial["run_id"],
                                "status": current.get("status"),
                                "error": current.get("error", "Workflow did not complete"),
                            },
                            default=str,
                        )
                        + "\n\n"
                    )
                    return
            await asyncio.sleep(0.5)
        timeout_event = {
            "event": "error",
            "run_id": initial["run_id"],
            "error": "Workflow status polling timed out",
        }
        yield f"data: {json.dumps(timeout_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
