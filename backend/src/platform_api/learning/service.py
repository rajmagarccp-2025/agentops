from platform_api.config import get_settings
from platform_api.learning.repository import SqlAlchemyLearningRepository
from platform_api.learning.schemas import (
    LearningFeedbackCreate,
    LearningRecord,
    VerificationResult,
    new_id,
    now,
)
from platform_api.remediation.schemas import RemediationRecord


class LearningService:
    def __init__(self) -> None:
        self.verifications: dict[str, dict[str, VerificationResult]] = {}
        self.feedback: dict[str, list[LearningRecord]] = {}
        self._database = None if get_settings().demo_mode else SqlAlchemyLearningRepository()

    def verify(self, record: RemediationRecord) -> VerificationResult:
        before = {"latency_p95_ms": 840.0, "error_rate_percent": 8.4}
        after = (
            {"latency_p95_ms": 220.0, "error_rate_percent": 1.2}
            if record.verified
            else before.copy()
        )
        deltas = {key: round(after[key] - value, 2) for key, value in before.items()}
        recovered = record.verified and after["error_rate_percent"] < 2.0
        result = VerificationResult(
            id=new_id(),
            tenant_id=record.tenant_id,
            remediation_id=record.id,
            recovered=recovered,
            confidence=0.93 if recovered else 0.35,
            metrics_before=before,
            metrics_after=after,
            deltas=deltas,
            message=(
                "Service health recovered after the controlled remediation."
                if recovered
                else "Recovery was not verified from the available signals."
            ),
            verified_at=now(),
        )
        self.verifications.setdefault(record.tenant_id, {})[record.id] = result
        if self._database is not None:
            self._database.add_verification(result)
        return result

    def add_feedback(self, tenant_id: str, payload: LearningFeedbackCreate) -> LearningRecord:
        record = LearningRecord(
            **payload.model_dump(),
            id=new_id(),
            tenant_id=tenant_id,
            created_at=now(),
        )
        self.feedback.setdefault(tenant_id, []).append(record)
        if self._database is not None:
            self._database.add_feedback(record)
        return record

    def list_verifications(self, tenant_id: str) -> list[VerificationResult]:
        if self._database is not None:
            return []
        return list(self.verifications.get(tenant_id, {}).values())

    def list_feedback(self, tenant_id: str) -> list[LearningRecord]:
        if self._database is not None:
            return self._database.list_feedback(tenant_id)
        return list(self.feedback.get(tenant_id, []))


learning_service = LearningService()
