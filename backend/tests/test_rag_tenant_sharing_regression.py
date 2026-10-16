"""Mandatory RAG Regression Test Suite — Tenant and Hierarchy Sharing Access Control.

Proves the 12 mandatory RAG access control and isolation requirements:
1. User can upload a document into an authorized organization/project/environment.
2. The uploader can retrieve the document when permitted.
3. A permitted project in the same organization can retrieve an explicitly shared document.
4. An unshared project in the same organization cannot retrieve it.
5. An explicitly permitted environment can retrieve it.
6. An unauthorized environment cannot retrieve it.
7. A user in another organization cannot retrieve it.
8. Cross-organization sharing is rejected with HTTP 403.
9. Forged tenant, project, environment, document, and sharing identifiers do not bypass authorization.
10. Revoking sharing removes access, including through caches and retrieval indexes.
11. An agent cannot retrieve a document its trusted execution context is not authorized to access.
12. Unauthorized retrieval returns no document text, chunks, embeddings-derived content, or citations disclosing protected information.
"""

import pytest
from fastapi.testclient import TestClient

from platform_api.database import SessionLocal
from platform_api.identity_repository import (
    EnvironmentRepository,
    ProjectRepository,
    TenantRepository,
)
from platform_api.main import app
from platform_api.rag_service.service import retrieve
from platform_api.security import issue_user_token

client = TestClient(app)

ORG_ALPHA = "org-alpha-rag-test"
ORG_BETA = "org-beta-rag-test"

# Global IDs to be initialized
PROJ_A1 = "proj-alpha-1"
PROJ_A2 = "proj-alpha-2"
PROJ_A3 = "proj-alpha-3"
ENV_A1_PROD = "env-alpha-1-prod"
ENV_A1_STAGING = "env-alpha-1-staging"
ENV_A1_DEV = "env-alpha-1-dev"
ENV_A2_DEV = "env-alpha-2-dev"

PROJ_B1 = "proj-beta-1"
ENV_B1_PROD = "env-beta-1-prod"


from platform_api.identity_models import EnvironmentModel, Project, Tenant

@pytest.fixture(scope="session", autouse=True)
def setup_tenants_and_projects():
    """Ensure database has the test organizations, projects, and environments seeded."""
    db = SessionLocal()
    tenant_repo = TenantRepository()
    project_repo = ProjectRepository()
    env_repo = EnvironmentRepository()

    try:
        # Org Alpha
        t_alpha = tenant_repo.get_tenant_by_id(db, ORG_ALPHA) or tenant_repo.get_tenant_by_slug(db, ORG_ALPHA)
        if not t_alpha:
            t_alpha = Tenant(id=ORG_ALPHA, name="Alpha Corp", slug=ORG_ALPHA)
            db.add(t_alpha)
            db.flush()

        p_a1 = project_repo.get_project_by_id(db, PROJ_A1)
        if not p_a1:
            p_a1 = Project(id=PROJ_A1, tenant_id=ORG_ALPHA, name="Project A1", slug="proj-a1")
            db.add(p_a1)
            db.flush()

        p_a2 = project_repo.get_project_by_id(db, PROJ_A2)
        if not p_a2:
            p_a2 = Project(id=PROJ_A2, tenant_id=ORG_ALPHA, name="Project A2", slug="proj-a2")
            db.add(p_a2)
            db.flush()

        p_a3 = project_repo.get_project_by_id(db, PROJ_A3)
        if not p_a3:
            p_a3 = Project(id=PROJ_A3, tenant_id=ORG_ALPHA, name="Project A3", slug="proj-a3")
            db.add(p_a3)
            db.flush()

        # Environments for Org Alpha
        for env_id, name, p_id in [
            (ENV_A1_PROD, "Production", PROJ_A1),
            (ENV_A1_STAGING, "Staging", PROJ_A1),
            (ENV_A1_DEV, "Development", PROJ_A1),
            (ENV_A2_DEV, "Development", PROJ_A2),
        ]:
            e = env_repo.get_environment_by_id(db, env_id)
            if not e:
                e = EnvironmentModel(id=env_id, tenant_id=ORG_ALPHA, project_id=p_id, name=name, slug=env_id)
                db.add(e)
                db.flush()

        # Org Beta
        t_beta = tenant_repo.get_tenant_by_id(db, ORG_BETA) or tenant_repo.get_tenant_by_slug(db, ORG_BETA)
        if not t_beta:
            t_beta = Tenant(id=ORG_BETA, name="Beta Corp", slug=ORG_BETA)
            db.add(t_beta)
            db.flush()

        p_b1 = project_repo.get_project_by_id(db, PROJ_B1)
        if not p_b1:
            p_b1 = Project(id=PROJ_B1, tenant_id=ORG_BETA, name="Project B1", slug="proj-b1")
            db.add(p_b1)
            db.flush()

        e_b1 = env_repo.get_environment_by_id(db, ENV_B1_PROD)
        if not e_b1:
            e_b1 = EnvironmentModel(id=ENV_B1_PROD, tenant_id=ORG_BETA, project_id=PROJ_B1, name="Production", slug=ENV_B1_PROD)
            db.add(e_b1)
            db.flush()

        db.commit()
    finally:
        db.close()


def auth_header(
    *permissions: str,
    tenant_id: str = ORG_ALPHA,
    project_id: str | None = PROJ_A1,
    environment_id: str | None = ENV_A1_PROD,
    roles: tuple[str, ...] = ("admin", "sre"),
) -> dict[str, str]:
    token = issue_user_token(
        subject="test-engineer",
        email="engineer@test.local",
        tenant_id=tenant_id,
        permissions=permissions or ("rag:read", "rag:write"),
        roles=roles,
        project_id=project_id,
        environment_id=environment_id,
    )
    return {"Authorization": f"Bearer {token}"}


# -----------------------------------------------------------------------------
# 1. User can upload a document into an authorized org/project/environment
# -----------------------------------------------------------------------------
def test_01_user_uploads_document_into_authorized_org_project_env():
    """Verify document upload derives tenant, project, and environment from verified principal context."""
    resp = client.post(
        "/api/v1/rag/documents",
        headers=auth_header("rag:write", tenant_id=ORG_ALPHA, project_id=PROJ_A1, environment_id=ENV_A1_PROD),
        json={
            "source": "runbooks/database_failover.md",
            "title": "Alpha Primary DB Failover Runbook",
            "content": (
                "Alpha confidential database failover SOP: "
                "Step 1: Check replication lag on replica-01. "
                "Step 2: Promote replica-01 via Patroni cluster leader switch."
            ),
            "document_type": "runbook",
            "service": "alpha-db",
            "environment": "production",
            "tags": ["patroni", "postgres", "failover"],
            "allowed_roles": ["sre", "admin"],
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] is not None
    assert data["tenant_id"] == ORG_ALPHA
    assert data["project_id"] == PROJ_A1
    assert data["environment_id"] == ENV_A1_PROD
    assert data["title"] == "Alpha Primary DB Failover Runbook"


# -----------------------------------------------------------------------------
# 2. Uploader can retrieve the document when permitted
# -----------------------------------------------------------------------------
def test_02_uploader_can_retrieve_document_when_permitted():
    """Verify uploader within matching tenant, project, and environment can retrieve the document."""
    retrieval = client.post(
        "/api/v1/rag/retrieve",
        headers=auth_header("rag:read", tenant_id=ORG_ALPHA, project_id=PROJ_A1, environment_id=ENV_A1_PROD),
        json={"query": "Patroni cluster leader switch failover", "limit": 3},
    )
    assert retrieval.status_code == 200
    data = retrieval.json()
    assert len(data["citations"]) >= 1
    assert any(c["title"] == "Alpha Primary DB Failover Runbook" for c in data["citations"])
    assert "Patroni cluster leader switch" in data["context"]


# -----------------------------------------------------------------------------
# 3. Permitted project in same organization can retrieve explicitly shared document
# -----------------------------------------------------------------------------
def test_03_permitted_project_same_org_can_retrieve_explicitly_shared_doc():
    """Verify sharing a document with another project in the same organization grants retrieval access."""
    # First, list documents to get the document ID
    docs_resp = client.get(
        "/api/v1/rag/documents",
        headers=auth_header("rag:read", tenant_id=ORG_ALPHA, project_id=PROJ_A1, environment_id=ENV_A1_PROD),
    )
    assert docs_resp.status_code == 200
    doc = next(d for d in docs_resp.json() if d["title"] == "Alpha Primary DB Failover Runbook")
    doc_id = doc["id"]

    # Share with Project A2
    share_resp = client.post(
        f"/api/v1/rag/documents/{doc_id}/shares",
        headers=auth_header("rag:write", tenant_id=ORG_ALPHA, project_id=PROJ_A1, environment_id=ENV_A1_PROD),
        json={"target_project_id": PROJ_A2, "target_environment_id": None},
    )
    assert share_resp.status_code == 201, share_resp.text
    share_data = share_resp.json()
    assert share_data["document_id"] == doc_id
    assert share_data["target_project_id"] == PROJ_A2

    # Query from Project A2
    retrieval = client.post(
        "/api/v1/rag/retrieve",
        headers=auth_header("rag:read", tenant_id=ORG_ALPHA, project_id=PROJ_A2, environment_id=ENV_A2_DEV),
        json={"query": "Patroni cluster leader switch failover", "limit": 3},
    )
    assert retrieval.status_code == 200
    data = retrieval.json()
    assert len(data["citations"]) >= 1
    assert any(c["title"] == "Alpha Primary DB Failover Runbook" for c in data["citations"])
    assert "Patroni cluster leader switch" in data["context"]


# -----------------------------------------------------------------------------
# 4. Unshared project in same organization cannot retrieve it
# -----------------------------------------------------------------------------
def test_04_unshared_project_same_org_cannot_retrieve():
    """Verify an unshared project in the same organization cannot retrieve the document."""
    retrieval = client.post(
        "/api/v1/rag/retrieve",
        headers=auth_header("rag:read", tenant_id=ORG_ALPHA, project_id=PROJ_A3, environment_id="env-a3"),
        json={"query": "Patroni cluster leader switch failover", "limit": 3},
    )
    assert retrieval.status_code == 200
    data = retrieval.json()
    assert data["citations"] == []
    assert data["context"] == ""


# -----------------------------------------------------------------------------
# 5. Explicitly permitted environment can retrieve it
# -----------------------------------------------------------------------------
def test_05_explicitly_permitted_environment_can_retrieve():
    """Verify sharing with a specific environment grants retrieval to that environment."""
    docs_resp = client.get(
        "/api/v1/rag/documents",
        headers=auth_header("rag:read", tenant_id=ORG_ALPHA, project_id=PROJ_A1, environment_id=ENV_A1_PROD),
    )
    doc = next(d for d in docs_resp.json() if d["title"] == "Alpha Primary DB Failover Runbook")
    doc_id = doc["id"]

    # Share specifically with Staging environment in Project A1
    share_resp = client.post(
        f"/api/v1/rag/documents/{doc_id}/shares",
        headers=auth_header("rag:write", tenant_id=ORG_ALPHA, project_id=PROJ_A1, environment_id=ENV_A1_PROD),
        json={"target_project_id": PROJ_A1, "target_environment_id": ENV_A1_STAGING},
    )
    assert share_resp.status_code == 201

    # Staging environment retrieves successfully
    retrieval = client.post(
        "/api/v1/rag/retrieve",
        headers=auth_header("rag:read", tenant_id=ORG_ALPHA, project_id=PROJ_A1, environment_id=ENV_A1_STAGING),
        json={"query": "Patroni cluster leader switch failover", "limit": 3},
    )
    assert retrieval.status_code == 200
    assert any(c["title"] == "Alpha Primary DB Failover Runbook" for c in retrieval.json()["citations"])


# -----------------------------------------------------------------------------
# 6. Unauthorized environment cannot retrieve it
# -----------------------------------------------------------------------------
def test_06_unauthorized_environment_cannot_retrieve():
    """Verify an environment without permission or share cannot retrieve the document."""
    retrieval = client.post(
        "/api/v1/rag/retrieve",
        headers=auth_header("rag:read", tenant_id=ORG_ALPHA, project_id=PROJ_A1, environment_id=ENV_A1_DEV),
        json={"query": "Patroni cluster leader switch failover", "limit": 3},
    )
    assert retrieval.status_code == 200
    data = retrieval.json()
    assert data["citations"] == []
    assert data["context"] == ""


# -----------------------------------------------------------------------------
# 7. User in another organization cannot retrieve it
# -----------------------------------------------------------------------------
def test_07_user_in_another_organization_cannot_retrieve():
    """Verify a user in another organization is completely isolated and cannot retrieve the document."""
    retrieval = client.post(
        "/api/v1/rag/retrieve",
        headers=auth_header("rag:read", tenant_id=ORG_BETA, project_id=PROJ_B1, environment_id=ENV_B1_PROD),
        json={"query": "Patroni cluster leader switch failover Alpha confidential", "limit": 5},
    )
    assert retrieval.status_code == 200
    data = retrieval.json()
    assert data["citations"] == []
    assert data["context"] == ""


# -----------------------------------------------------------------------------
# 8. Cross-organization sharing is rejected
# -----------------------------------------------------------------------------
def test_08_cross_organization_sharing_is_rejected():
    """Verify attempting to share a document across organization boundaries is strictly forbidden with HTTP 403."""
    docs_resp = client.get(
        "/api/v1/rag/documents",
        headers=auth_header("rag:read", tenant_id=ORG_ALPHA, project_id=PROJ_A1, environment_id=ENV_A1_PROD),
    )
    doc = next(d for d in docs_resp.json() if d["title"] == "Alpha Primary DB Failover Runbook")
    doc_id = doc["id"]

    # Attempt to share Org Alpha's document with Project B1 (belonging to Org Beta)
    share_resp = client.post(
        f"/api/v1/rag/documents/{doc_id}/shares",
        headers=auth_header("rag:write", tenant_id=ORG_ALPHA, project_id=PROJ_A1, environment_id=ENV_A1_PROD),
        json={"target_project_id": PROJ_B1, "target_environment_id": None},
    )
    assert share_resp.status_code == 403
    assert "Cross-organization sharing is forbidden" in share_resp.json()["detail"]


# -----------------------------------------------------------------------------
# 9. Forged tenant, project, environment, document, and sharing identifiers do not bypass authorization
# -----------------------------------------------------------------------------
def test_09_forged_identifiers_do_not_bypass_authorization():
    """Verify forged headers or cross-tenant document manipulation cannot bypass server-side validation."""
    docs_resp = client.get(
        "/api/v1/rag/documents",
        headers=auth_header("rag:read", tenant_id=ORG_ALPHA, project_id=PROJ_A1, environment_id=ENV_A1_PROD),
    )
    doc = next(d for d in docs_resp.json() if d["title"] == "Alpha Primary DB Failover Runbook")
    doc_id = doc["id"]

    # Scenario A: Org Beta user sends forged x-tenant-id pointing to Org Alpha
    headers = auth_header("rag:read", tenant_id=ORG_BETA, project_id=PROJ_B1, environment_id=ENV_B1_PROD)
    headers["X-Tenant-Id"] = ORG_ALPHA
    headers["X-Project-Id"] = PROJ_A1
    headers["X-Environment-Id"] = ENV_A1_PROD

    spoofed_retrieve = client.post(
        "/api/v1/rag/retrieve",
        headers=headers,
        json={"query": "Patroni cluster leader switch failover"},
    )
    assert spoofed_retrieve.status_code == 200
    assert spoofed_retrieve.json()["citations"] == []

    # Scenario B: Org Beta user attempts to inspect or delete shares of Org Alpha's document
    shares_resp = client.get(
        f"/api/v1/rag/documents/{doc_id}/shares",
        headers=auth_header("rag:read", tenant_id=ORG_BETA, project_id=PROJ_B1, environment_id=ENV_B1_PROD),
    )
    assert shares_resp.status_code == 404

    # Scenario C: Non-existent or mismatched target environment during share
    invalid_share = client.post(
        f"/api/v1/rag/documents/{doc_id}/shares",
        headers=auth_header("rag:write", tenant_id=ORG_ALPHA, project_id=PROJ_A1, environment_id=ENV_A1_PROD),
        json={"target_project_id": PROJ_A1, "target_environment_id": "non-existent-env"},
    )
    assert invalid_share.status_code in (400, 403)


# -----------------------------------------------------------------------------
# 10. Revoking sharing removes access, including through caches and retrieval indexes
# -----------------------------------------------------------------------------
def test_10_revoking_sharing_removes_access():
    """Verify that deleting a share immediately removes retrieval access."""
    docs_resp = client.get(
        "/api/v1/rag/documents",
        headers=auth_header("rag:read", tenant_id=ORG_ALPHA, project_id=PROJ_A1, environment_id=ENV_A1_PROD),
    )
    doc = next(d for d in docs_resp.json() if d["title"] == "Alpha Primary DB Failover Runbook")
    doc_id = doc["id"]

    # List shares
    shares = client.get(
        f"/api/v1/rag/documents/{doc_id}/shares",
        headers=auth_header("rag:read", tenant_id=ORG_ALPHA, project_id=PROJ_A1, environment_id=ENV_A1_PROD),
    ).json()

    a2_shares = [s for s in shares if s["target_project_id"] == PROJ_A2]
    assert len(a2_shares) >= 1
    share_id = a2_shares[0]["id"]

    # Revoke share for Project A2
    del_resp = client.delete(
        f"/api/v1/rag/documents/{doc_id}/shares/{share_id}",
        headers=auth_header("rag:write", tenant_id=ORG_ALPHA, project_id=PROJ_A1, environment_id=ENV_A1_PROD),
    )
    assert del_resp.status_code == 204

    # Immediate subsequent retrieval from Project A2 must return empty
    retrieval = client.post(
        "/api/v1/rag/retrieve",
        headers=auth_header("rag:read", tenant_id=ORG_ALPHA, project_id=PROJ_A2, environment_id=ENV_A2_DEV),
        json={"query": "Patroni cluster leader switch failover", "limit": 3},
    )
    assert retrieval.status_code == 200
    assert retrieval.json()["citations"] == []
    assert retrieval.json()["context"] == ""


# -----------------------------------------------------------------------------
# 11. An agent cannot retrieve a document its trusted execution context is not authorized to access
# -----------------------------------------------------------------------------
def test_11_agent_cannot_retrieve_unauthorized_document():
    """Verify agent execution context enforces the exact same tenant and workspace boundaries."""
    # Agent running with Org Beta execution context
    agent_res_beta = retrieve(
        tenant_id=ORG_BETA,
        roles=frozenset(["sre", "user"]),
        query="Patroni cluster leader switch failover",
        limit=3,
        project_id=PROJ_B1,
        environment_id=ENV_B1_PROD,
    )
    assert len(agent_res_beta.citations) == 0
    assert agent_res_beta.context == ""

    # Agent running with Org Alpha but unshared Project A3
    agent_res_unshared = retrieve(
        tenant_id=ORG_ALPHA,
        roles=frozenset(["sre", "user"]),
        query="Patroni cluster leader switch failover",
        limit=3,
        project_id=PROJ_A3,
        environment_id="env-a3",
    )
    assert len(agent_res_unshared.citations) == 0
    assert agent_res_unshared.context == ""

    # Agent running with authorized Org Alpha / Project A1 / Prod context
    agent_res_authorized = retrieve(
        tenant_id=ORG_ALPHA,
        roles=frozenset(["sre", "user"]),
        query="Patroni cluster leader switch failover",
        limit=3,
        project_id=PROJ_A1,
        environment_id=ENV_A1_PROD,
    )
    assert len(agent_res_authorized.citations) >= 1
    assert "Patroni cluster leader switch" in agent_res_authorized.context


# -----------------------------------------------------------------------------
# 12. Unauthorized retrieval returns no document text, chunks, embeddings, or citations
# -----------------------------------------------------------------------------
def test_12_unauthorized_retrieval_returns_no_disclosures():
    """Verify that unauthorized requests receive zero disclosures (no titles, chunk IDs, snippets, or text)."""
    retrieval = client.post(
        "/api/v1/rag/retrieve",
        headers=auth_header("rag:read", tenant_id=ORG_BETA, project_id=PROJ_B1, environment_id=ENV_B1_PROD),
        json={"query": "database failover switch patroni", "limit": 10},
    )
    assert retrieval.status_code == 200
    res = retrieval.json()
    assert res["citations"] == []
    assert res["context"] == ""
    # Verify no leaks in raw JSON representation
    raw_text = retrieval.text
    assert "Alpha Primary DB Failover Runbook" not in raw_text
    assert "Patroni cluster leader switch" not in raw_text
    assert "replica-01" not in raw_text
