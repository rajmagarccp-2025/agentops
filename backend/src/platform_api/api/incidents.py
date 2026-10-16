from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from platform_api.agents.service import agent_runtime
from platform_api.incidents.schemas import CorrelatedIncident, IncidentCreate, IncidentRecord
from platform_api.incidents.service import (
    collect_and_correlate,
    create_incident,
    incident_repository,
)
from platform_api.security import Principal, require_permission

router = APIRouter(prefix="/incidents", tags=["incidents"])


class InvestigationResponse(BaseModel):
    incident: CorrelatedIncident
    run_id: str
    status: str
    findings: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    steps: list[dict[str, object]] = Field(default_factory=list)


@router.post("", response_model=IncidentRecord)
async def ingest_incident(
    body: IncidentCreate,
    principal: Annotated[Principal, Depends(require_permission("incidents:write"))],
) -> IncidentRecord:
    return create_incident(principal.tenant_id, body)


@router.get("", response_model=list[IncidentRecord])
async def list_incidents(
    principal: Annotated[Principal, Depends(require_permission("incidents:read"))],
) -> list[IncidentRecord]:
    return incident_repository.list(principal.tenant_id)


@router.get("/{incident_id}", response_model=IncidentRecord)
async def get_incident(
    incident_id: str,
    principal: Annotated[Principal, Depends(require_permission("incidents:read"))],
) -> IncidentRecord:
    try:
        return incident_repository.get(principal.tenant_id, incident_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        ) from exc


@router.post(
    "/{incident_id}/investigate",
    response_model=InvestigationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def investigate_incident(
    incident_id: str,
    principal: Annotated[Principal, Depends(require_permission("incidents:investigate"))],
) -> InvestigationResponse:
    try:
        correlated = collect_and_correlate(principal.tenant_id, incident_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        ) from exc
    state = agent_runtime.run(
        request=correlated.incident.description or correlated.incident.title,
        request_type="investigation",
        tenant_id=principal.tenant_id,
        subject=principal.subject,
        permissions=list(principal.permissions),
        initial_evidence=correlated.evidence,
        run_id=f"incident-{incident_id}",
    )
    return InvestigationResponse(
        incident=correlated,
        run_id=state["run_id"],
        status=state.get("status", "unknown"),
        findings=state.get("findings", []),
        recommendation=state.get("recommendation"),
        steps=state.get("steps", []),
    )
