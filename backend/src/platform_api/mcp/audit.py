import logging
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from platform_api.database import SessionLocal
from platform_api.identity_repository import AuditLogRepository

logger = logging.getLogger("platform_api.mcp.audit")


@dataclass(frozen=True)
class ToolAuditEvent:
    execution_id: str
    tenant_id: str
    subject: str
    tool_name: str
    risk: str
    parameters: dict[str, Any]
    outcome: str
    request_id: str
    created_at: datetime
    project_id: str | None = None
    environment_id: str | None = None
    actor_email: str | None = None


class AuditSink(Protocol):
    def record(self, event: ToolAuditEvent) -> None: ...


class InMemoryAuditSink:
    def __init__(self) -> None:
        self.events: list[ToolAuditEvent] = []

    def record(self, event: ToolAuditEvent) -> None:
        self.events.append(event)


class DatabaseAuditSink:
    """Persist tool execution audit events to the durable platform audit log."""

    def __init__(self) -> None:
        self.events: deque[ToolAuditEvent] = deque(maxlen=1_000)

    def record(self, event: ToolAuditEvent) -> None:
        try:
            with SessionLocal() as db:
                AuditLogRepository().record_event(
                    session=db,
                    actor=event.subject,
                    action=f"tool.{event.outcome}",
                    resource_type="tool_call",
                    resource_id=event.execution_id,
                    organization_id=event.tenant_id,
                    project_id=event.project_id,
                    environment_id=event.environment_id,
                    actor_email=event.actor_email,
                    details={
                        "tool_name": event.tool_name,
                        "risk": event.risk,
                        "parameters": event.parameters,
                        "outcome": event.outcome,
                        "request_id": event.request_id,
                        "created_at": event.created_at.isoformat(),
                    },
                )
                db.commit()
        except Exception as exc:
            logger.exception("Failed to persist tool execution audit event %s", event.execution_id)
            raise RuntimeError(
                f"Could not persist tool execution audit event {event.execution_id}"
            ) from exc
        self.events.append(event)


def create_audit_event(
    execution_id: str,
    tenant_id: str,
    subject: str,
    tool_name: str,
    risk: str,
    parameters: dict[str, Any],
    outcome: str,
    request_id: str,
    *,
    project_id: str | None = None,
    environment_id: str | None = None,
    actor_email: str | None = None,
) -> ToolAuditEvent:
    return ToolAuditEvent(
        execution_id=execution_id,
        tenant_id=tenant_id,
        subject=subject,
        tool_name=tool_name,
        risk=risk,
        parameters=parameters,
        outcome=outcome,
        request_id=request_id,
        created_at=datetime.now(UTC),
        project_id=project_id,
        environment_id=environment_id,
        actor_email=actor_email,
    )
