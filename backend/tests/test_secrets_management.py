from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from platform_api.database import Base, get_db
from platform_api.identity_repository import (
    EnvironmentRepository,
    MembershipRepository,
    ProjectRepository,
    TenantRepository,
)
from platform_api.main import app
from platform_api.secrets import service as secret_service
from platform_api.secrets.crypto import InternalCryptoService
from platform_api.secrets.providers import adapters as secret_provider_adapters
from platform_api.secrets.providers.base import validate_provider_endpoint_ssrf
from platform_api.security import issue_user_token

client = TestClient(app)


def test_external_secret_provider_scaffolds_are_disabled_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        secret_provider_adapters,
        "get_settings",
        lambda: SimpleNamespace(app_env="production"),
    )
    with pytest.raises(HTTPException) as exc:
        secret_provider_adapters.get_secret_provider_adapter(
            SimpleNamespace(provider_type="aws_secrets_manager")
        )
    assert exc.value.status_code == 503


def test_secret_version_restore_creates_a_new_version_and_is_audited() -> None:
    ctx = _setup_org_and_users()
    provider_id = client.get(
        "/api/v1/secret-providers", headers=ctx["headers_admin"]
    ).json()[0]["id"]
    created = client.post(
        "/api/v1/secrets",
        headers=ctx["headers_admin"],
        json={
            "name": "ROLLBACK_TEST_SECRET",
            "provider_id": provider_id,
            "scope": "organization",
            "value": "original-version",
        },
    )
    assert created.status_code == 201
    secret_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/secrets/{secret_id}",
        headers=ctx["headers_admin"],
        json={"value": "updated-version"},
    )
    assert updated.status_code == 200
    assert updated.json()["current_version_num"] == 2

    denied = client.post(
        f"/api/v1/secrets/{secret_id}/versions/1/restore",
        headers=ctx["headers_reader"],
    )
    assert denied.status_code == 403

    restored = client.post(
        f"/api/v1/secrets/{secret_id}/versions/1/restore",
        headers=ctx["headers_admin"],
    )
    assert restored.status_code == 200
    assert restored.json()["current_version_num"] == 3

    revealed = client.post(f"/api/v1/secrets/{secret_id}/reveal", headers=ctx["headers_admin"])
    assert revealed.status_code == 200
    assert revealed.json()["value"] == "original-version"

    audit = client.get(
        f"/api/v1/secrets/{secret_id}/audit", headers=ctx["headers_admin"]
    )
    assert "secret.version_restored" in [event["action"] for event in audit.json()]


@pytest.fixture(autouse=True)
def setup_test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


def _setup_org_and_users():
    """Provision tenant, project, environments, role users, and a second tenant."""
    from platform_api.database import get_db

    db = next(app.dependency_overrides[get_db]())

    # Tenant 1
    t1 = TenantRepository().create_tenant(db, name="Acme Corp", slug="acme-corp")
    p1 = ProjectRepository().create_project(
        db, tenant_id=t1.id, name="AI Platform", slug="ai-platform"
    )
    env_prod = EnvironmentRepository().create_environment(
        db, tenant_id=t1.id, project_id=p1.id, name="Production", slug="prod", env_type="Production"
    )
    env_dev = EnvironmentRepository().create_environment(
        db,
        tenant_id=t1.id,
        project_id=p1.id,
        name="Development",
        slug="dev",
        env_type="Development",
    )

    # Tenant 2 (Isolation Test)
    t2 = TenantRepository().create_tenant(db, name="Stark Industries", slug="stark-ind")

    # Users
    u_admin = MembershipRepository().create_user_with_password(
        db, "Alice Admin", "admin@acme.com", "SecretPass123!"
    )
    MembershipRepository().add_organization_member(db, t1.id, u_admin.id, "ADMIN", is_owner=True)

    u_dev = MembershipRepository().create_user_with_password(
        db, "Bob Dev", "dev@acme.com", "SecretPass123!"
    )
    MembershipRepository().add_organization_member(db, t1.id, u_dev.id, "DEVELOPER")

    u_reader = MembershipRepository().create_user_with_password(
        db, "Carol Reader", "reader@acme.com", "SecretPass123!"
    )
    MembershipRepository().add_organization_member(db, t1.id, u_reader.id, "READER")

    u_runtime = MembershipRepository().create_user_with_password(
        db, "Service Agent", "agent@acme.com", "SecretPass123!"
    )
    MembershipRepository().add_organization_member(db, t1.id, u_runtime.id, "RUNTIME_CONSUMER")

    db.commit()

    # Tokens
    tok_admin = issue_user_token(
        u_admin.id,
        u_admin.email,
        t1.id,
        roles=["ADMIN"],
        project_id=p1.id,
        environment_id=env_prod.id,
    )
    tok_dev = issue_user_token(
        u_dev.id,
        u_dev.email,
        t1.id,
        roles=["DEVELOPER"],
        project_id=p1.id,
        environment_id=env_dev.id,
    )
    tok_reader = issue_user_token(
        u_reader.id,
        u_reader.email,
        t1.id,
        roles=["READER"],
        project_id=p1.id,
        environment_id=env_prod.id,
    )
    tok_runtime = issue_user_token(
        u_runtime.id,
        u_runtime.email,
        t1.id,
        roles=["RUNTIME_CONSUMER"],
        project_id=p1.id,
        environment_id=env_prod.id,
    )
    tok_tenant2 = issue_user_token(u_admin.id, u_admin.email, t2.id, roles=["ADMIN"])

    return {
        "tenant1_id": t1.id,
        "project1_id": p1.id,
        "env_prod_id": env_prod.id,
        "env_dev_id": env_dev.id,
        "tenant2_id": t2.id,
        "headers_admin": {"Authorization": f"Bearer {tok_admin}"},
        "headers_dev": {"Authorization": f"Bearer {tok_dev}"},
        "headers_reader": {"Authorization": f"Bearer {tok_reader}"},
        "headers_runtime": {"Authorization": f"Bearer {tok_runtime}"},
        "headers_tenant2": {"Authorization": f"Bearer {tok_tenant2}"},
    }


def test_1_authorized_secret_creation_and_list():
    ctx = _setup_org_and_users()

    # Get default provider
    prov_res = client.get("/api/v1/secret-providers", headers=ctx["headers_admin"])
    assert prov_res.status_code == 200
    providers = prov_res.json()
    assert len(providers) >= 1
    provider_id = providers[0]["id"]

    # Create secret as Admin
    create_res = client.post(
        "/api/v1/secrets",
        headers=ctx["headers_admin"],
        json={
            "name": "OPENAI_API_KEY",
            "description": "Production LLM API Key",
            "secret_type": "api_key",
            "provider_id": provider_id,
            "scope": "environment",
            "project_id": ctx["project1_id"],
            "environment_id": ctx["env_prod_id"],
            "value": "sk-proj-prod-super-secret-key-123456789",
            "metadata": {"model": "gpt-4o"},
        },
    )
    assert create_res.status_code == 201
    sec = create_res.json()
    assert sec["name"] == "OPENAI_API_KEY"
    assert "value" not in sec  # Secret values must be write-only in list & metadata!

    # List secret metadata
    list_res = client.get("/api/v1/secrets", headers=ctx["headers_admin"])
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 1
    assert items[0]["name"] == "OPENAI_API_KEY"
    assert "value" not in items[0]


def test_2_secret_value_reveal_and_audit():
    ctx = _setup_org_and_users()
    prov_id = client.get("/api/v1/secret-providers", headers=ctx["headers_admin"]).json()[0]["id"]

    create_res = client.post(
        "/api/v1/secrets",
        headers=ctx["headers_admin"],
        json={
            "name": "DB_PASSWORD",
            "secret_type": "database_credential",
            "provider_id": prov_id,
            "scope": "organization",
            "value": "PostgresDbPassword99!",
        },
    )
    sec_id = create_res.json()["id"]

    # Reveal value as Admin
    reveal_res = client.post(f"/api/v1/secrets/{sec_id}/reveal", headers=ctx["headers_admin"])
    assert reveal_res.status_code == 200
    rev_data = reveal_res.json()
    assert rev_data["value"] == "PostgresDbPassword99!"

    # Verify audit event recorded
    audit_res = client.get(f"/api/v1/secrets/{sec_id}/audit", headers=ctx["headers_admin"])
    assert audit_res.status_code == 200
    audit_events = audit_res.json()
    actions = [a["action"] for a in audit_events]
    assert "secret.created" in actions
    assert "secret.value_revealed" in actions
    for a in audit_events:
        assert "PostgresDbPassword99!" not in str(a)  # Redaction check


def test_3_developer_permissions_and_deletion_restriction():
    ctx = _setup_org_and_users()
    prov_id = client.get("/api/v1/secret-providers", headers=ctx["headers_admin"]).json()[0]["id"]

    # Create secret as Admin
    sec_id = client.post(
        "/api/v1/secrets",
        headers=ctx["headers_admin"],
        json={
            "name": "DEV_SECRET",
            "provider_id": prov_id,
            "scope": "organization",
            "value": "DevVal123",
        },
    ).json()["id"]

    # Developer update value is allowed
    upd_res = client.patch(
        f"/api/v1/secrets/{sec_id}",
        headers=ctx["headers_dev"],
        json={"value": "UpdatedDevVal456"},
    )
    assert upd_res.status_code == 200

    # Developer delete attempt must fail with 403 Forbidden
    del_res = client.delete(f"/api/v1/secrets/{sec_id}", headers=ctx["headers_dev"])
    assert del_res.status_code == 403


def test_4_reader_permissions():
    ctx = _setup_org_and_users()
    prov_id = client.get("/api/v1/secret-providers", headers=ctx["headers_admin"]).json()[0]["id"]

    sec_id = client.post(
        "/api/v1/secrets",
        headers=ctx["headers_admin"],
        json={
            "name": "READ_ONLY_SEC",
            "provider_id": prov_id,
            "scope": "organization",
            "value": "ReadOnlyVal",
        },
    ).json()["id"]

    # Reader can view metadata
    meta_res = client.get(f"/api/v1/secrets/{sec_id}", headers=ctx["headers_reader"])
    assert meta_res.status_code == 200

    # Reader reveal value fails with 403 Forbidden
    rev_res = client.post(f"/api/v1/secrets/{sec_id}/reveal", headers=ctx["headers_reader"])
    assert rev_res.status_code == 403


def test_5_entity_assignment_and_runtime_resolution(monkeypatch: pytest.MonkeyPatch):
    class MemorySecretCache:
        def __init__(self) -> None:
            self.values: dict[tuple[str, str], tuple[str, str]] = {}
            self.reads = 0
            self.hits = 0

        def get(self, tenant_id: str, secret_id: str, version_id: str) -> str | None:
            self.reads += 1
            cached = self.values.get((tenant_id, secret_id))
            if cached and cached[0] == version_id:
                self.hits += 1
                return cached[1]
            return None

        def set(self, tenant_id: str, secret_id: str, version_id: str, value: str) -> None:
            self.values[(tenant_id, secret_id)] = (version_id, value)

        def invalidate(self, tenant_id: str, secret_id: str) -> None:
            self.values.pop((tenant_id, secret_id), None)

    cache = MemorySecretCache()
    monkeypatch.setattr(secret_service, "get_secret_resolution_cache", lambda: cache)
    ctx = _setup_org_and_users()
    prov_id = client.get("/api/v1/secret-providers", headers=ctx["headers_admin"]).json()[0]["id"]

    sec_id = client.post(
        "/api/v1/secrets",
        headers=ctx["headers_admin"],
        json={
            "name": "AGENT_MODEL_KEY",
            "provider_id": prov_id,
            "scope": "environment",
            "value": "KeyForAgentOnly",
        },
    ).json()["id"]

    # Assign secret to SRE Agent
    asgn_res = client.post(
        f"/api/v1/secrets/{sec_id}/assignments",
        headers=ctx["headers_admin"],
        json={
            "entity_type": "agent",
            "entity_id": "sre-agent-01",
            "entity_name": "Autopilot SRE Agent",
        },
    )
    assert asgn_res.status_code == 201

    # Runtime Resolution for assigned agent succeeds
    res_ok = client.post(
        "/api/v1/secrets/resolve",
        headers=ctx["headers_runtime"],
        json={
            "secret_identifier": "AGENT_MODEL_KEY",
            "requesting_entity_type": "agent",
            "requesting_entity_id": "sre-agent-01",
        },
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["value"] == "KeyForAgentOnly"

    res_cached = client.post(
        "/api/v1/secrets/resolve",
        headers=ctx["headers_runtime"],
        json={
            "secret_identifier": "AGENT_MODEL_KEY",
            "requesting_entity_type": "agent",
            "requesting_entity_id": "sre-agent-01",
        },
    )
    assert res_cached.status_code == 200
    assert cache.reads == 2
    assert cache.hits == 1

    # Runtime Resolution for unassigned agent fails
    res_deny = client.post(
        "/api/v1/secrets/resolve",
        headers=ctx["headers_runtime"],
        json={
            "secret_identifier": "AGENT_MODEL_KEY",
            "requesting_entity_type": "agent",
            "requesting_entity_id": "unauthorized-agent-99",
        },
    )
    assert res_deny.status_code == 403
    assert cache.reads == 2


def test_6_tenant_and_scope_isolation():
    ctx = _setup_org_and_users()
    prov_id = client.get("/api/v1/secret-providers", headers=ctx["headers_admin"]).json()[0]["id"]

    sec_id = client.post(
        "/api/v1/secrets",
        headers=ctx["headers_admin"],
        json={
            "name": "TENANT1_SECRET",
            "provider_id": prov_id,
            "scope": "organization",
            "value": "Tenant1Data",
        },
    ).json()["id"]

    # Cross-tenant access attempt by Tenant 2 admin fails
    t2_res = client.get(f"/api/v1/secrets/{sec_id}", headers=ctx["headers_tenant2"])
    assert t2_res.status_code == 403


def test_7_secret_rotation():
    ctx = _setup_org_and_users()
    prov_id = client.get("/api/v1/secret-providers", headers=ctx["headers_admin"]).json()[0]["id"]

    sec = client.post(
        "/api/v1/secrets",
        headers=ctx["headers_admin"],
        json={
            "name": "ROTATING_SECRET",
            "provider_id": prov_id,
            "scope": "organization",
            "value": "OriginalVal1",
        },
    ).json()

    # Rotate secret
    rot_res = client.post(f"/api/v1/secrets/{sec['id']}/rotate", headers=ctx["headers_admin"])
    assert rot_res.status_code == 200
    assert rot_res.json()["current_version_num"] == 2


def test_10_secret_revocation_blocks_resolution_and_reactivation():
    ctx = _setup_org_and_users()
    provider_id = client.get(
        "/api/v1/secret-providers", headers=ctx["headers_admin"]
    ).json()[0]["id"]
    secret = client.post(
        "/api/v1/secrets",
        headers=ctx["headers_admin"],
        json={
            "name": "REVOKED_SECRET",
            "provider_id": provider_id,
            "scope": "organization",
            "value": "must-not-be-returned",
        },
    ).json()

    revoked = client.post(
        f"/api/v1/secrets/{secret['id']}/revoke",
        headers=ctx["headers_admin"],
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    metadata = client.get(
        f"/api/v1/secrets/{secret['id']}", headers=ctx["headers_admin"]
    )
    assert metadata.status_code == 200
    assert metadata.json()["status"] == "revoked"

    resolution = client.post(
        "/api/v1/secrets/resolve",
        headers=ctx["headers_runtime"],
        json={"secret_identifier": secret["id"]},
    )
    assert resolution.status_code == 403

    reactivation = client.patch(
        f"/api/v1/secrets/{secret['id']}",
        headers=ctx["headers_admin"],
        json={"status": "active"},
    )
    assert reactivation.status_code == 409


def test_8_ssrf_endpoint_protection():
    restricted_endpoints = (
        "http://127.0.0.1:8080/internal-vault",
        "http://10.0.0.1/internal-vault",
        "http://[fd00::1]/internal-vault",
        "http://metadata.google.internal/computeMetadata/v1",
    )
    for endpoint in restricted_endpoints:
        with pytest.raises(ValueError, match="restricted"):
            validate_provider_endpoint_ssrf(endpoint)


def test_9_internal_crypto_aes256gcm():
    plaintext = "super-secret-key-phrase-12345"
    enc_val, meta = InternalCryptoService.encrypt(plaintext)
    assert meta["algorithm"] == "AES-256-GCM"
    decrypted = InternalCryptoService.decrypt(enc_val, meta)
    assert decrypted == plaintext
