from sqlalchemy import select

from platform_api.config import get_settings
from platform_api.database import SessionLocal
from platform_api.llmops_service.models import EvaluationResultModel, PromptVersionModel
from platform_api.llmops_service.schemas import EvaluationResult, PromptVersion


class LLMOpsRepository:
    def __init__(self) -> None:
        self.prompts: dict[str, list[PromptVersion]] = {}
        self.evaluations: dict[str, list[EvaluationResult]] = {}

    def add_prompt(self, prompt: PromptVersion) -> PromptVersion:
        self.prompts.setdefault(prompt.tenant_id, []).append(prompt)
        return prompt

    def add_evaluation(self, result: EvaluationResult) -> EvaluationResult:
        self.evaluations.setdefault(result.tenant_id, []).append(result)
        return result

    def list_prompts(self, tenant_id: str) -> list[PromptVersion]:
        return list(self.prompts.get(tenant_id, []))

    def list_evaluations(self, tenant_id: str) -> list[EvaluationResult]:
        return list(self.evaluations.get(tenant_id, []))


class SqlAlchemyLLMOpsRepository(LLMOpsRepository):
    def add_prompt(self, prompt: PromptVersion) -> PromptVersion:
        model = PromptVersionModel(
            id=prompt.id,
            tenant_id=prompt.tenant_id,
            name=prompt.name,
            version=prompt.version,
            template=prompt.template,
            metadata_json=prompt.metadata,
            created_at=prompt.created_at,
        )
        with SessionLocal() as session:
            session.add(model)
            session.commit()
        return prompt

    def add_evaluation(self, result: EvaluationResult) -> EvaluationResult:
        model = EvaluationResultModel(**result.model_dump())
        with SessionLocal() as session:
            session.add(model)
            session.commit()
        return result

    def list_prompts(self, tenant_id: str) -> list[PromptVersion]:
        with SessionLocal() as session:
            models = session.scalars(
                select(PromptVersionModel)
                .where(PromptVersionModel.tenant_id == tenant_id)
                .order_by(PromptVersionModel.created_at.desc())
            ).all()
            return [
                PromptVersion(
                    id=model.id,
                    tenant_id=model.tenant_id,
                    name=model.name,
                    version=model.version,
                    template=model.template,
                    metadata=model.metadata_json,
                    created_at=model.created_at,
                )
                for model in models
            ]

    def list_evaluations(self, tenant_id: str) -> list[EvaluationResult]:
        with SessionLocal() as session:
            models = session.scalars(
                select(EvaluationResultModel)
                .where(EvaluationResultModel.tenant_id == tenant_id)
                .order_by(EvaluationResultModel.created_at.desc())
            ).all()
            return [
                EvaluationResult(
                    id=model.id,
                    tenant_id=model.tenant_id,
                    dataset=model.dataset,
                    model=model.model,
                    correctness=model.correctness,
                    groundedness=model.groundedness,
                    retrieval_quality=model.retrieval_quality,
                    tool_call_correctness=model.tool_call_correctness,
                    latency_ms=model.latency_ms,
                    estimated_cost_usd=model.estimated_cost_usd,
                    success=model.success,
                    created_at=model.created_at,
                )
                for model in models
            ]


llmops_repository = LLMOpsRepository() if get_settings().demo_mode else SqlAlchemyLLMOpsRepository()
