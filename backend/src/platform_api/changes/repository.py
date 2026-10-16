from uuid import uuid4

from sqlalchemy import select

from platform_api.changes.models import ChangeEventModel
from platform_api.changes.schemas import ChangeEvent, ChangeEventCreate, ChangeType
from platform_api.config import get_settings
from platform_api.database import SessionLocal


class InMemoryChangeRepository:
    def __init__(self) -> None:
        self._events: dict[str, dict[str, ChangeEvent]] = {}

    def create(self, tenant_id: str, payload: ChangeEventCreate) -> ChangeEvent:
        event = ChangeEvent(**payload.model_dump(), id=str(uuid4()), tenant_id=tenant_id)
        self._events.setdefault(tenant_id, {})[event.id] = event
        return event

    def list_for_service(self, tenant_id: str, service: str) -> list[ChangeEvent]:
        return sorted(
            [
                event
                for event in self._events.get(tenant_id, {}).values()
                if event.service == service
            ],
            key=lambda event: event.occurred_at,
        )

    def list_for_tenant(self, tenant_id: str) -> list[ChangeEvent]:
        return sorted(
            self._events.get(tenant_id, {}).values(),
            key=lambda event: event.occurred_at,
            reverse=True,
        )


class SqlAlchemyChangeRepository(InMemoryChangeRepository):
    def create(self, tenant_id: str, payload: ChangeEventCreate) -> ChangeEvent:
        model = ChangeEventModel(**payload.model_dump(), tenant_id=tenant_id)
        with SessionLocal() as session:
            session.add(model)
            session.commit()
            session.refresh(model)
            return _to_event(model)

    def list_for_service(self, tenant_id: str, service: str) -> list[ChangeEvent]:
        with SessionLocal() as session:
            models = session.scalars(
                select(ChangeEventModel)
                .where(
                    ChangeEventModel.tenant_id == tenant_id,
                    ChangeEventModel.service == service,
                )
                .order_by(ChangeEventModel.occurred_at)
            ).all()
            return [_to_event(model) for model in models]

    def list_for_tenant(self, tenant_id: str) -> list[ChangeEvent]:
        with SessionLocal() as session:
            models = session.scalars(
                select(ChangeEventModel)
                .where(ChangeEventModel.tenant_id == tenant_id)
                .order_by(ChangeEventModel.occurred_at.desc())
            ).all()
            return [_to_event(model) for model in models]


def _to_event(model: ChangeEventModel) -> ChangeEvent:
    return ChangeEvent(
        id=model.id,
        tenant_id=model.tenant_id,
        service=model.service,
        environment=model.environment,
        change_type=ChangeType(model.change_type),
        title=model.title,
        occurred_at=model.occurred_at,
        source=model.source,
        actor=model.actor,
        details=model.details,
    )


change_repository = (
    InMemoryChangeRepository() if get_settings().demo_mode else SqlAlchemyChangeRepository()
)
