from fastapi.testclient import TestClient

from platform_api.main import app
from platform_api.security import issue_user_token

client = TestClient(app)


def auth_header(
    *permissions: str,
    tenant_id: str = "rag-tenant",
    project_id: str | None = "rag-project",
    environment_id: str | None = "rag-environment",
    roles: tuple[str, ...] = (),
) -> dict[str, str]:
    token = issue_user_token(
        subject="rag-test-user",
        email="rag-test-user@example.test",
        tenant_id=tenant_id,
        permissions=permissions,
        roles=roles,
        project_id=project_id,
        environment_id=environment_id,
    )
    return {"Authorization": f"Bearer {token}"}


def test_ingestion_chunks_and_retrieval_returns_citations() -> None:
    response = client.post(
        "/api/v1/rag/documents",
        headers=auth_header("rag:write"),
        json={
            "source": "runbooks/checkout.md",
            "title": "Checkout latency runbook",
            "content": (
                "Check database connection pool saturation. Compare deployment latency. "
                "Roll back only after approval."
            ),
            "document_type": "runbook",
            "service": "checkout-api",
            "environment": "production",
            "tags": ["latency", "database"],
            "allowed_roles": ["sre"],
        },
    )
    assert response.status_code == 200

    retrieval = client.post(
        "/api/v1/rag/retrieve",
        headers=auth_header("rag:read", tenant_id="rag-tenant", roles=("sre",)),
        json={"query": "database connection pool latency", "limit": 3},
    )
    assert retrieval.status_code == 200
    payload = retrieval.json()
    assert len(payload["citations"]) == 1
    assert payload["citations"][0]["title"] == "Checkout latency runbook"
    assert "connection pool" in payload["context"]


def test_retrieval_enforces_tenant_isolation() -> None:
    retrieval = client.post(
        "/api/v1/rag/retrieve",
        headers=auth_header("rag:read", tenant_id="other-rag-tenant"),
        json={"query": "database connection pool", "limit": 3},
    )
    assert retrieval.status_code == 200
    assert retrieval.json()["citations"] == []


def test_retrieval_requires_permission() -> None:
    response = client.post(
        "/api/v1/rag/retrieve",
        headers=auth_header("incidents:read"),
        json={"query": "runbook", "limit": 3},
    )
    assert response.status_code == 403


def test_retrieval_is_scoped_to_project_and_environment() -> None:
    headers = auth_header("rag:write")
    created = client.post(
        "/api/v1/rag/documents",
        headers=headers,
        json={
            "source": "env-runbook.md",
            "title": "Environment-only evidence",
            "content": "A unique phrase for environment isolation checks.",
            "document_type": "runbook",
        },
    )
    assert created.status_code == 200

    other_environment = client.post(
        "/api/v1/rag/retrieve",
        headers=auth_header(
            "rag:read",
            project_id="rag-project",
            environment_id="another-environment",
        ),
        json={"query": "unique phrase environment isolation"},
    )
    assert other_environment.status_code == 200
    assert other_environment.json()["citations"] == []

    other_project = client.post(
        "/api/v1/rag/retrieve",
        headers=auth_header(
            "rag:read",
            project_id="another-project",
            environment_id="rag-environment",
        ),
        json={"query": "unique phrase environment isolation"},
    )
    assert other_project.status_code == 200
    assert other_project.json()["citations"] == []


def test_rag_requires_selected_project_and_environment() -> None:
    response = client.post(
        "/api/v1/rag/retrieve",
        headers=auth_header("rag:read", project_id=None, environment_id=None),
        json={"query": "workspace-specific knowledge"},
    )
    assert response.status_code == 409
