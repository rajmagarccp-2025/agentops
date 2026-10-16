import pytest
from fastapi.testclient import TestClient

from platform_api.database import SessionLocal, init_db
from platform_api.identity_models import Tenant
from platform_api.main import app
from platform_api.security import issue_demo_token

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    with SessionLocal() as db:
        for t_id, t_name, t_slug in [
            ("tenant-dell", "Dell Technologies", "dell-technologies"),
            ("tenant-competitor", "Competitor Tenant", "competitor-tenant"),
        ]:
            if not db.query(Tenant).filter_by(id=t_id).first():
                db.add(Tenant(id=t_id, name=t_name, slug=t_slug))
        db.commit()


def auth_header(
    subject: str = "test-user-1",
    tenant_id: str = "tenant-dell",
    permissions: list[str] | None = None,
    roles: list[str] | None = None,
) -> dict[str, str]:
    token = issue_demo_token(
        subject=subject,
        tenant_id=tenant_id,
        permissions=permissions or ["llm:read", "llm:write", "llm:invoke", "llm:evaluate"],
        roles=roles or ["developer"],
    )
    return {"Authorization": f"Bearer {token}"}


def test_multi_model_registration_and_masked_credentials() -> None:
    # 1. Register OpenAI Model
    response = client.post(
        "/api/v1/llmops/models",
        headers=auth_header(subject="creator-admin-1"),
        json={
            "provider": "openai",
            "model_name": "gpt-4o",
            "display_name": "Production Reasoning Engine",
            "description": "Primary GPT-4o model for org reasoning tasks",
            "api_key": "sk-proj-testkey1234567890abcdef",
            "organization_wide": True,
            "capabilities": ["chat", "structured_output", "tool_calling"],
            "test_connection_first": False,
        },
    )
    assert response.status_code == 200
    model = response.json()
    assert model["provider"] == "openai"
    assert model["model_name"] == "gpt-4o"
    assert model["credential_status"] == "configured"
    assert model["credential_masked"] == "●●●●●●●●"
    assert "sk-proj" not in str(model)  # Secret API Key must NEVER be returned in plaintext

    # 2. Register Anthropic Model
    resp_claude = client.post(
        "/api/v1/llmops/models",
        headers=auth_header(subject="creator-admin-1"),
        json={
            "provider": "anthropic",
            "model_name": "claude-3-5-sonnet",
            "display_name": "Claude 3.5 Sonnet",
            "api_key": "sk-ant-testkey987654321",
            "organization_wide": True,
            "capabilities": ["chat", "vision"],
            "test_connection_first": False,
        },
    )
    assert resp_claude.status_code == 200
    model_claude = resp_claude.json()
    assert model_claude["provider"] == "anthropic"


def test_model_admin_permissions_and_ownership() -> None:
    # 1. Creator registers model and becomes Model Administrator
    create_res = client.post(
        "/api/v1/llmops/models",
        headers=auth_header(subject="user-admin-owner"),
        json={
            "provider": "google_gemini",
            "model_name": "gemini-1.5-pro",
            "display_name": "Gemini 1.5 Pro Model",
            "api_key": "AIzaSyTestKeyGemini12345",
            "organization_wide": True,
            "test_connection_first": False,
        },
    )
    assert create_res.status_code == 200
    model = create_res.json()
    model_id = model["id"]
    assert model["is_administrator"] is True

    # 2. Non-admin user attempts to update model configuration -> 403 Forbidden
    update_res = client.patch(
        f"/api/v1/llmops/models/{model_id}",
        headers=auth_header(subject="unauthorized-user-2"),
        json={"display_name": "Hacked Model Name"},
    )
    assert update_res.status_code == 403

    # 3. Model Administrator assigns second user as Model Admin
    assign_res = client.post(
        f"/api/v1/llmops/models/{model_id}/admins",
        headers=auth_header(subject="user-admin-owner"),
        json={"user_id": "user-coadmin-2"},
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["user_id"] == "user-coadmin-2"

    # 4. Newly assigned Co-Admin can now update configuration
    update_coadmin_res = client.patch(
        f"/api/v1/llmops/models/{model_id}",
        headers=auth_header(subject="user-coadmin-2"),
        json={"display_name": "Updated by CoAdmin"},
    )
    assert update_coadmin_res.status_code == 200
    assert update_coadmin_res.json()["display_name"] == "Updated by CoAdmin"


def test_explicit_deny_and_access_policy_sharing() -> None:
    # 1. Register Model
    reg_res = client.post(
        "/api/v1/llmops/models",
        headers=auth_header(subject="policy-owner"),
        json={
            "provider": "aws_bedrock",
            "model_name": "anthropic.claude-3-haiku-20240307-v1:0",
            "display_name": "Bedrock Claude Haiku",
            "api_key": "AKIAIOSFODNN7EXAMPLE",
            "organization_wide": True,
            "test_connection_first": False,
        },
    )
    model_id = reg_res.json()["id"]

    # 2. Grant explicit DENY policy for target user "blocked-user-99"
    deny_res = client.post(
        f"/api/v1/llmops/models/{model_id}/policies",
        headers=auth_header(subject="policy-owner"),
        json={
            "grantee_type": "user",
            "grantee_id": "blocked-user-99",
            "permission": "use",
            "effect": "deny",
        },
    )
    assert deny_res.status_code == 200

    # 3. Blocked user attempts to invoke model -> 403 Explicit Deny Rejection
    inv_res = client.post(
        "/v1/chat/completions",
        headers=auth_header(subject="blocked-user-99"),
        json={
            "model": model_id,
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert inv_res.status_code == 403
    assert "Access Denied" in inv_res.json()["detail"]


def test_scope_authorization_and_cross_tenant_isolation() -> None:
    # 1. Register Model in tenant-dell
    reg_res = client.post(
        "/api/v1/llmops/models",
        headers=auth_header(subject="dell-admin", tenant_id="tenant-dell"),
        json={
            "provider": "openai",
            "model_name": "gpt-4o-mini",
            "display_name": "Dell Isolated Model",
            "api_key": "sk-dellkey123",
            "test_connection_first": False,
        },
    )
    model_id = reg_res.json()["id"]

    # 2. Invocation attempt from different tenant (tenant-competitor) -> 404/403 Forbidden
    cross_res = client.post(
        "/v1/chat/completions",
        headers=auth_header(subject="competitor-user", tenant_id="tenant-competitor"),
        json={
            "model": model_id,
            "messages": [{"role": "user", "content": "Cross tenant attempt"}],
        },
    )
    assert cross_res.status_code in (403, 404)


def test_credential_rotation() -> None:
    # 1. Register Model
    reg_res = client.post(
        "/api/v1/llmops/models",
        headers=auth_header(subject="key-rotator"),
        json={
            "provider": "custom_openai",
            "model_name": "llama-3-70b-instruct",
            "display_name": "Local Llama 3 Endpoint",
            "api_key": "old-secret-key-1111",
            "test_connection_first": False,
        },
    )
    model_id = reg_res.json()["id"]

    # 2. Rotate API Credential
    rot_res = client.post(
        f"/api/v1/llmops/models/{model_id}/credentials",
        headers=auth_header(subject="key-rotator"),
        json={
            "api_key": "new-secret-key-2222",
            "test_connection": False,
        },
    )
    assert rot_res.status_code == 200
    assert rot_res.json()["credential_status"] == "configured"
    assert "new-secret" not in str(
        rot_res.json()
    )  # Secret API Key must NEVER be returned in plaintext


def test_unified_gateway_chat_completion_invocation() -> None:
    # 1. Register Model
    reg_res = client.post(
        "/api/v1/llmops/models",
        headers=auth_header(subject="chat-invoker"),
        json={
            "provider": "mock",
            "model_name": "mock-test-model",
            "display_name": "Mock Test Gateway Model",
            "api_key": "mock-api-key-9999",
            "test_connection_first": False,
        },
    )
    model_id = reg_res.json()["id"]

    # 2. Invoke Gateway via /v1/chat/completions
    inv_res = client.post(
        "/v1/chat/completions",
        headers=auth_header(subject="chat-invoker"),
        json={
            "model": model_id,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Summarize gateway performance."},
            ],
            "temperature": 0.5,
        },
    )
    assert inv_res.status_code == 200
    payload = inv_res.json()
    assert payload["object"] == "chat.completion"
    assert len(payload["choices"]) > 0
    assert payload["usage"]["total_tokens"] > 0
    assert payload["latency_ms"] >= 0
    assert payload["estimated_cost_usd"] >= 0
