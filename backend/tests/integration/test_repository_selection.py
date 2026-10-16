import pytest

from platform_api.changes.repository import SqlAlchemyChangeRepository
from platform_api.finops.repository import SqlAlchemyFinOpsRepository
from platform_api.governance.repository import SqlAlchemyApprovalRepository
from platform_api.incidents.repository import SqlAlchemyIncidentRepository
from platform_api.inventory.repository import SqlAlchemyInventoryRepository
from platform_api.learning.repository import SqlAlchemyLearningRepository
from platform_api.llmops_service.repository import SqlAlchemyLLMOpsRepository
from platform_api.rag_service.repository import SqlAlchemyRagRepository
from platform_api.remediation.repository import SqlAlchemyRemediationRepository
from platform_api.security_investigation.repository import SqlAlchemySecurityEventRepository


@pytest.mark.integration
def test_production_repository_implementations_are_available() -> None:
    repositories = (
        SqlAlchemyChangeRepository,
        SqlAlchemyFinOpsRepository,
        SqlAlchemyApprovalRepository,
        SqlAlchemyIncidentRepository,
        SqlAlchemyInventoryRepository,
        SqlAlchemyLearningRepository,
        SqlAlchemyLLMOpsRepository,
        SqlAlchemyRagRepository,
        SqlAlchemyRemediationRepository,
        SqlAlchemySecurityEventRepository,
    )

    assert all(repository for repository in repositories)
