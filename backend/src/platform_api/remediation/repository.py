from sqlalchemy import select

from platform_api.database import SessionLocal
from platform_api.remediation.models import RemediationActionModel
from platform_api.remediation.schemas import RemediationAction, RemediationRecord


class SqlAlchemyRemediationRepository:
    def create(self, record: RemediationRecord) -> RemediationRecord:
        model = RemediationActionModel(
            id=record.id,
            tenant_id=record.tenant_id,
            action=record.action.value,
            parameters=record.parameters,
            status=record.status,
            execution_id=record.execution_id,
            idempotency_key=record.idempotency_key,
            created_at=record.created_at,
            verified=record.verified,
            verification_message=record.verification_message,
        )
        with SessionLocal() as session:
            session.add(model)
            session.commit()
        return record

    def get_by_id(self, tenant_id: str, record_id: str) -> RemediationRecord:
        with SessionLocal() as session:
            model = session.scalar(
                select(RemediationActionModel).where(
                    RemediationActionModel.tenant_id == tenant_id,
                    RemediationActionModel.id == record_id,
                )
            )
            if model is None:
                raise KeyError(record_id)
            return _to_record(model)

    def get_by_idempotency(self, tenant_id: str, key: str) -> RemediationRecord | None:
        with SessionLocal() as session:
            model = session.scalar(
                select(RemediationActionModel).where(
                    RemediationActionModel.tenant_id == tenant_id,
                    RemediationActionModel.idempotency_key == key,
                )
            )
            return _to_record(model) if model else None

    def update(self, record: RemediationRecord) -> RemediationRecord:
        with SessionLocal() as session:
            model = session.get(RemediationActionModel, record.id)
            if model is None or model.tenant_id != record.tenant_id:
                raise KeyError(record.id)
            model.status = record.status
            model.verified = record.verified
            model.verification_message = record.verification_message
            session.commit()
        return record


def _to_record(model: RemediationActionModel) -> RemediationRecord:
    return RemediationRecord(
        id=model.id,
        tenant_id=model.tenant_id,
        action=RemediationAction(model.action),
        parameters=model.parameters,
        status=model.status,
        execution_id=model.execution_id,
        idempotency_key=model.idempotency_key,
        created_at=model.created_at,
        verified=model.verified,
        verification_message=model.verification_message,
    )
