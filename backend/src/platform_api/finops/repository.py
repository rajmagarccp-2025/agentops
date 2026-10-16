from uuid import uuid4

from sqlalchemy import select

from platform_api.config import get_settings
from platform_api.database import SessionLocal
from platform_api.finops.models import CostRecordModel, UtilizationRecordModel
from platform_api.finops.schemas import (
    CostRecord,
    CostRecordCreate,
    FinOpsRecommendation,
    UtilizationCreate,
    UtilizationRecord,
)


class FinOpsRepository:
    def __init__(self) -> None:
        self.costs: dict[str, list[CostRecord]] = {}
        self.utilization: dict[str, list[UtilizationRecord]] = {}
        self.recommendations: dict[str, list[FinOpsRecommendation]] = {}

    def add_cost(self, tenant_id: str, payload: CostRecordCreate) -> CostRecord:
        record = CostRecord(**payload.model_dump(), id=str(uuid4()), tenant_id=tenant_id)
        self.costs.setdefault(tenant_id, []).append(record)
        return record

    def add_utilization(self, tenant_id: str, payload: UtilizationCreate) -> UtilizationRecord:
        record = UtilizationRecord(**payload.model_dump(), id=str(uuid4()), tenant_id=tenant_id)
        self.utilization.setdefault(tenant_id, []).append(record)
        return record

    def add_recommendation(self, recommendation: FinOpsRecommendation) -> FinOpsRecommendation:
        self.recommendations.setdefault(recommendation.tenant_id, []).append(recommendation)
        return recommendation

    def get_costs(self, tenant_id: str) -> list[CostRecord]:
        return list(self.costs.get(tenant_id, []))

    def get_utilization(self, tenant_id: str) -> list[UtilizationRecord]:
        return list(self.utilization.get(tenant_id, []))

    def get_recommendations(self, tenant_id: str) -> list[FinOpsRecommendation]:
        return list(self.recommendations.get(tenant_id, []))


class SqlAlchemyFinOpsRepository(FinOpsRepository):
    def add_cost(self, tenant_id: str, payload: CostRecordCreate) -> CostRecord:
        model = CostRecordModel(**payload.model_dump(), tenant_id=tenant_id)
        with SessionLocal() as session:
            session.add(model)
            session.commit()
            session.refresh(model)
            return CostRecord(**payload.model_dump(), id=model.id, tenant_id=tenant_id)

    def add_utilization(self, tenant_id: str, payload: UtilizationCreate) -> UtilizationRecord:
        model = UtilizationRecordModel(**payload.model_dump(), tenant_id=tenant_id)
        with SessionLocal() as session:
            session.add(model)
            session.commit()
            session.refresh(model)
            return UtilizationRecord(**payload.model_dump(), id=model.id, tenant_id=tenant_id)

    def get_costs(self, tenant_id: str) -> list[CostRecord]:
        with SessionLocal() as session:
            models = session.scalars(
                select(CostRecordModel)
                .where(CostRecordModel.tenant_id == tenant_id)
                .order_by(CostRecordModel.period)
            ).all()
            return [
                CostRecord(
                    id=model.id,
                    tenant_id=model.tenant_id,
                    period=model.period,
                    provider=model.provider,
                    account=model.account,
                    service=model.service,
                    environment=model.environment,
                    amount_usd=model.amount_usd,
                    metadata=model.metadata_json,
                )
                for model in models
            ]

    def get_utilization(self, tenant_id: str) -> list[UtilizationRecord]:
        with SessionLocal() as session:
            models = session.scalars(
                select(UtilizationRecordModel)
                .where(UtilizationRecordModel.tenant_id == tenant_id)
                .order_by(UtilizationRecordModel.observed_on)
            ).all()
            return [
                UtilizationRecord(
                    id=model.id,
                    tenant_id=model.tenant_id,
                    observed_on=model.observed_on,
                    resource_id=model.resource_id,
                    service=model.service,
                    environment=model.environment,
                    cpu_percent=model.cpu_percent,
                    memory_percent=model.memory_percent,
                    monthly_cost_usd=model.monthly_cost_usd,
                    metadata=model.metadata_json,
                )
                for model in models
            ]


finops_repository = FinOpsRepository() if get_settings().demo_mode else SqlAlchemyFinOpsRepository()
