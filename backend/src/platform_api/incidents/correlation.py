from datetime import timedelta
from typing import Any

from platform_api.incidents.schemas import CorrelatedIncident, IncidentRecord, TimelineEvent


def correlate_incident(
    incident: IncidentRecord,
    telemetry: dict[str, Any],
    changes: list[dict[str, Any]],
) -> CorrelatedIncident:
    timeline = [
        TimelineEvent(
            timestamp=incident.started_at - timedelta(minutes=5),
            event_type="metric",
            title="Latency crossed service threshold",
            source="observability.mock",
            evidence={"p95_ms": telemetry.get("latency_p95_ms", 840)},
        ),
        TimelineEvent(
            timestamp=incident.started_at,
            event_type="incident",
            title=incident.title,
            source="itsm.api",
            evidence={"severity": incident.severity.value},
        ),
    ]
    timeline.extend(
        TimelineEvent(
            timestamp=change.get("occurred_at", incident.started_at - timedelta(minutes=2)),
            event_type=str(change.get("change_type", "change")),
            title=str(change.get("title", "Configuration change observed")),
            source=str(change.get("source", "change.mock")),
            evidence=change,
        )
        for change in changes
    )
    timeline.sort(key=lambda event: event.timestamp)
    evidence: list[dict[str, Any]] = [
        {"source": "observability.mock", "type": "telemetry", "data": telemetry},
        {"source": "change.mock", "type": "changes", "data": changes},
    ]
    return CorrelatedIncident(
        incident=incident,
        timeline=timeline,
        evidence=evidence,
        hypotheses=[
            "The recent checkout-api deployment is temporally correlated with latency degradation.",
            "Database connection pool saturation may be contributing to elevated request latency.",
        ],
        confidence=0.72,
        recommended_steps=[
            "Compare checkout-api v2.18.4 error and latency metrics with the previous version.",
            "Inspect database connection pool utilization and saturation events.",
            "Validate dependency health before selecting remediation.",
        ],
    )
