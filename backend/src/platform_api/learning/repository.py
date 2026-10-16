from sqlalchemy import select

from platform_api.database import SessionLocal
from platform_api.learning.models import LearningRecordModel, VerificationRecordModel
from platform_api.learning.schemas import LearningRecord, VerificationResult


class SqlAlchemyLearningRepository:
    def add_verification(self, result: VerificationResult) -> VerificationResult:
        model = VerificationRecordModel(**result.model_dump())
        with SessionLocal() as session:
            session.add(model)
            session.commit()
        return result

    def add_feedback(self, record: LearningRecord) -> LearningRecord:
        model = LearningRecordModel(**record.model_dump())
        with SessionLocal() as session:
            session.add(model)
            session.commit()
        return record

    def list_feedback(self, tenant_id: str) -> list[LearningRecord]:
        with SessionLocal() as session:
            models = session.scalars(
                select(LearningRecordModel)
                .where(LearningRecordModel.tenant_id == tenant_id)
                .order_by(LearningRecordModel.created_at.desc())
            ).all()
            return [LearningRecord.model_validate(model, from_attributes=True) for model in models]
