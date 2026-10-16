from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from platform_api.database import SessionLocal
from platform_api.incidents.models import IncidentRecordModel
from platform_api.incidents.schemas import (
    IncidentCreate,
    IncidentRecord,
    IncidentSeverity,
    IncidentStatus,
)


class IncidentRepository:
    def create(self, tenant_id: str, payload: IncidentCreate) -> IncidentRecord:
        raise NotImplementedError

    def get(self, tenant_id: str, incident_id: str) -> IncidentRecord:
        raise NotImplementedError

    def list(self, tenant_id: str) -> list[IncidentRecord]:
        raise NotImplementedError


class InMemoryIncidentRepository(IncidentRepository):
    def __init__(self) -> None:
        self._records: dict[str, dict[str, IncidentRecord]] = {}

    def create(self, tenant_id: str, payload: IncidentCreate) -> IncidentRecord:
        record = IncidentRecord(
            **payload.model_dump(),
            id=str(uuid4()),
            tenant_id=tenant_id,
            status=IncidentStatus.OPEN,
            created_at=datetime.now(UTC),
        )
        self._records.setdefault(tenant_id, {})[record.id] = record
        return record

    def get(self, tenant_id: str, incident_id: str) -> IncidentRecord:
        try:
            return self._records[tenant_id][incident_id]
        except KeyError as exc:
            raise KeyError(incident_id) from exc

    def list(self, tenant_id: str) -> list[IncidentRecord]:
        return sorted(
            self._records.get(tenant_id, {}).values(),
            key=lambda record: record.started_at,
            reverse=True,
        )


class SqlAlchemyIncidentRepository(IncidentRepository):
    def create(self, tenant_id: str, payload: IncidentCreate) -> IncidentRecord:
        model = IncidentRecordModel(
            **payload.model_dump(),
            tenant_id=tenant_id,
            status=IncidentStatus.OPEN.value,
        )
        with SessionLocal() as session:
            session.add(model)
            session.commit()
            session.refresh(model)
            return _to_record(model)

    def get(self, tenant_id: str, incident_id: str) -> IncidentRecord:
        with SessionLocal() as session:
            model = session.scalar(
                select(IncidentRecordModel).where(
                    IncidentRecordModel.id == incident_id,
                    IncidentRecordModel.tenant_id == tenant_id,
                )
            )
            if model is None:
                raise KeyError(incident_id)
            return _to_record(model)

    def list(self, tenant_id: str) -> list[IncidentRecord]:
        with SessionLocal() as session:
            models = session.scalars(
                select(IncidentRecordModel)
                .where(IncidentRecordModel.tenant_id == tenant_id)
                .order_by(IncidentRecordModel.started_at.desc())
            ).all()
            return [_to_record(model) for model in models]


def _to_record(model: IncidentRecordModel) -> IncidentRecord:
    return IncidentRecord(
        id=model.id,
        tenant_id=model.tenant_id,
        title=model.title,
        service=model.service,
        severity=IncidentSeverity(model.severity),
        status=IncidentStatus(model.status),
        description=model.description,
        started_at=model.started_at,
        created_at=model.created_at,
    )
