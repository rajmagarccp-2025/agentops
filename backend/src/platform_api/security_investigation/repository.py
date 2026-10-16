from uuid import uuid4

from sqlalchemy import select

from platform_api.config import get_settings
from platform_api.database import SessionLocal
from platform_api.security_investigation.models import SecurityEventModel
from platform_api.security_investigation.schemas import (
    SecurityEvent,
    SecurityEventCreate,
    SecurityEventType,
)


class SecurityEventRepository:
    def __init__(self) -> None:
        self._events: dict[str, dict[str, SecurityEvent]] = {}

    def create(self, tenant_id: str, payload: SecurityEventCreate) -> SecurityEvent:
        event = SecurityEvent(**payload.model_dump(), id=str(uuid4()), tenant_id=tenant_id)
        self._events.setdefault(tenant_id, {})[event.id] = event
        return event

    def list_for_tenant(self, tenant_id: str) -> list[SecurityEvent]:
        return sorted(
            self._events.get(tenant_id, {}).values(),
            key=lambda event: event.occurred_at,
            reverse=True,
        )


class SqlAlchemySecurityEventRepository(SecurityEventRepository):
    def create(self, tenant_id: str, payload: SecurityEventCreate) -> SecurityEvent:
        model = SecurityEventModel(**payload.model_dump(), tenant_id=tenant_id)
        with SessionLocal() as session:
            session.add(model)
            session.commit()
            session.refresh(model)
            return SecurityEvent(**payload.model_dump(), id=model.id, tenant_id=tenant_id)

    def list_for_tenant(self, tenant_id: str) -> list[SecurityEvent]:
        with SessionLocal() as session:
            models = session.scalars(
                select(SecurityEventModel)
                .where(SecurityEventModel.tenant_id == tenant_id)
                .order_by(SecurityEventModel.occurred_at.desc())
            ).all()
            return [
                SecurityEvent(
                    id=model.id,
                    tenant_id=model.tenant_id,
                    event_type=SecurityEventType(model.event_type),
                    title=model.title,
                    service=model.service,
                    resource_id=model.resource_id,
                    actor=model.actor,
                    occurred_at=model.occurred_at,
                    severity=model.severity,
                    source=model.source,
                    details=model.details,
                )
                for model in models
            ]


security_event_repository = (
    SecurityEventRepository() if get_settings().demo_mode else SqlAlchemySecurityEventRepository()
)
