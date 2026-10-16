from platform_api.mcp.gateway import tool_registry
from platform_api.security import Principal
from platform_api.security_investigation.repository import security_event_repository
from platform_api.security_investigation.schemas import (
    SecurityEvent,
    SecurityEventCreate,
    SecurityFinding,
    SecurityInvestigation,
)


def ingest_event(tenant_id: str, payload: SecurityEventCreate) -> SecurityEvent:
    return security_event_repository.create(tenant_id, payload)


def investigate(tenant_id: str) -> SecurityInvestigation:
    events = security_event_repository.list_for_tenant(tenant_id)
    principal = Principal(
        subject="security-service",
        tenant_id=tenant_id,
        roles=frozenset(),
        permissions=frozenset({"tools:read"}),
    )
    external = tool_registry.execute(
        "security.get_events",
        {},
        principal,
        f"security-{tenant_id}",
        False,
    )
    if external.result is not None:
        events = events + [
            SecurityEvent(
                **event,
                id=f"mock-{index}",
                tenant_id=tenant_id,
            )
            for index, event in enumerate(external.result.data["events"])
        ]
    findings = [_finding(event) for event in events]
    return SecurityInvestigation(
        tenant_id=tenant_id,
        findings=findings,
        event_count=len(events),
        highest_severity=max((finding.severity for finding in findings), default=0),
    )


def _finding(event: SecurityEvent) -> SecurityFinding:
    if event.event_type.value == "policy_violation":
        action = "Review the policy violation and revoke or remediate the affected access."
    elif event.event_type.value == "suspicious_activity":
        action = (
            "Validate actor identity, rotate exposed credentials, and review related audit events."
        )
    elif event.event_type.value == "iam":
        action = "Review IAM permissions for least privilege and confirm the actor's business need."
    else:
        action = "Prioritize remediation according to the vulnerability severity and exposure."
    return SecurityFinding(
        event_id=event.id,
        title=event.title,
        severity=event.severity,
        confidence=0.88 if event.severity >= 4 else 0.71,
        evidence={
            "event_type": event.event_type.value,
            "actor": event.actor,
            "resource_id": event.resource_id,
            "source": event.source,
            "details": event.details,
        },
        recommended_action=action,
    )
