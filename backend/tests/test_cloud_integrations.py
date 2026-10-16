from uuid import uuid4

from fastapi.testclient import TestClient

from platform_api.database import SessionLocal
from platform_api.identity_models import EnvironmentModel, Project, Tenant
from platform_api.main import app
from platform_api.security import issue_user_token

client = TestClient(app)


def seed_workspace(
    tenant_id: str,
    project_id: str,
    environment_ids: tuple[str, ...],
) -> None:
    suffix = str(uuid4())
    with SessionLocal() as session:
        session.add(
            Tenant(id=tenant_id, name="Cloud integration test", slug=f"cloud-test-{suffix}")
        )
        session.flush()
        session.add(
            Project(
                id=project_id,
                tenant_id=tenant_id,
                name="Cloud project",
                slug=f"cloud-project-{suffix}",
            )
        )
        session.flush()
        session.add_all(
            [
                EnvironmentModel(
                    id=environment_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    name=f"Environment {index}",
                    slug=f"environment-{index}-{suffix}",
                    type="Development",
                )
                for index, environment_id in enumerate(environment_ids)
            ]
        )
        session.commit()


def auth_headers(
    permissions: tuple[str, ...],
    *,
    project_id: str,
    environment_id: str,
    tenant_id: str,
) -> dict[str, str]:
    token = issue_user_token(
        subject=f"cloud-test-{uuid4()}",
        email="cloud-test@example.test",
        tenant_id=tenant_id,
        permissions=permissions,
        project_id=project_id,
        environment_id=environment_id,
    )
    return {"Authorization": f"Bearer {token}"}


def test_cloud_integration_reference_is_scoped_and_unverified() -> None:
    project_id, environment_id, tenant_id = (str(uuid4()) for _ in range(3))
    other_environment_id = str(uuid4())
    seed_workspace(tenant_id, project_id, (environment_id, other_environment_id))
    headers = auth_headers(
        ("cloud:read", "cloud:manage"),
        project_id=project_id,
        environment_id=environment_id,
        tenant_id=tenant_id,
    )
    created = client.post(
        "/api/v1/cloud-integrations",
        headers=headers,
        json={
            "provider": "aws",
            "display_name": "Production read role",
            "account_id": f"account-{uuid4()}",
            "identity_reference": "arn:aws:iam::123456789012:role/AgenticSRE-ReadOnly",
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "unverified"
    assert "does not represent an authenticated" in created.json()["status_detail"]

    listed = client.get("/api/v1/cloud-integrations", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["connections"]) == 1
    assert all(not provider["verification_supported"] for provider in listed.json()["providers"])

    other_environment_headers = auth_headers(
        ("cloud:read", "cloud:manage"),
        project_id=project_id,
        environment_id=other_environment_id,
        tenant_id=tenant_id,
    )
    other_environment = client.get("/api/v1/cloud-integrations", headers=other_environment_headers)
    assert other_environment.status_code == 200
    assert other_environment.json()["connections"] == []

    denied_delete = client.delete(
        f"/api/v1/cloud-integrations/{created.json()['id']}",
        headers=other_environment_headers,
    )
    assert denied_delete.status_code == 404

    deleted = client.delete(
        f"/api/v1/cloud-integrations/{created.json()['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204


def test_cloud_integration_rejects_credential_material() -> None:
    headers = auth_headers(
        ("cloud:manage",),
        project_id=str(uuid4()),
        environment_id=str(uuid4()),
        tenant_id=str(uuid4()),
    )
    response = client.post(
        "/api/v1/cloud-integrations",
        headers=headers,
        json={
            "provider": "github",
            "display_name": "Do not store token",
            "account_id": "org-account",
            "identity_reference": "ghp_exampletokenvalue123",
        },
    )
    assert response.status_code == 422


def test_cloud_integration_requires_manage_permission() -> None:
    headers = auth_headers(
        ("cloud:read",),
        project_id=str(uuid4()),
        environment_id=str(uuid4()),
        tenant_id=str(uuid4()),
    )
    response = client.post(
        "/api/v1/cloud-integrations",
        headers=headers,
        json={
            "provider": "gcp",
            "display_name": "Read-only user",
            "account_id": "project-x",
            "identity_reference": "service-account@project-x.iam.gserviceaccount.com",
        },
    )
    assert response.status_code == 403
