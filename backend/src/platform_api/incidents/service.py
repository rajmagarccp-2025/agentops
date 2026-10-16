from datetime import timedelta

from platform_api.changes.repository import change_repository
from platform_api.config import get_settings
from platform_api.incidents.correlation import correlate_incident
from platform_api.incidents.repository import (
    IncidentRepository,
    InMemoryIncidentRepository,
    SqlAlchemyIncidentRepository,
)
from platform_api.incidents.schemas import CorrelatedIncident, IncidentCreate
from platform_api.mcp.gateway import tool_registry
from platform_api.security import Principal


def _repository() -> IncidentRepository:
    if get_settings().demo_mode:
        return InMemoryIncidentRepository()
    return SqlAlchemyIncidentRepository()


incident_repository = _repository()


def collect_and_correlate(tenant_id: str, incident_id: str) -> CorrelatedIncident:
    incident = incident_repository.get(tenant_id, incident_id)
    principal = Principal(
        subject="incident-service",
        tenant_id=tenant_id,
        roles=frozenset(),
        permissions=frozenset({"tools:read"}),
    )
    telemetry_execution = tool_registry.execute(
        "observability.get_incident_signals",
        {"service": incident.service},
        principal,
        incident_id,
        False,
    )
    telemetry = telemetry_execution.result.data if telemetry_execution.result else {}
    changes = [
        event.model_dump()
        for event in change_repository.list_for_service(tenant_id, incident.service)
    ]
    if not changes:
        changes = [
            {
                "change_type": "deployment",
                "title": "checkout-api v2.18.4 deployed",
                "source": "cicd.mock",
                "occurred_at": incident.started_at - timedelta(minutes=9),
                "details": {"version": "v2.18.4"},
            },
            {
                "change_type": "configuration",
                "title": "Runtime configuration updated",
                "source": "config.mock",
                "occurred_at": incident.started_at - timedelta(minutes=2),
                "details": {"setting": "connection_pool_size"},
            },
        ]
    return correlate_incident(incident, telemetry, changes)


def create_incident(tenant_id: str, payload: IncidentCreate):
    return incident_repository.create(tenant_id, payload)
