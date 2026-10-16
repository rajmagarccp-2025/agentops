import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from platform_api.config import Settings
from platform_api.identity_repository import ROLE_PERMISSIONS_MAP
from platform_api.main import app
from platform_api.security import (
    Principal,
    issue_demo_token,
    require_permission,
    require_role,
    verify_tenant_scope,
)

client = TestClient(app)


def test_write_roles_can_run_agents_but_read_roles_cannot() -> None:
    assert "agents:run" in ROLE_PERMISSIONS_MAP["WRITE"]
    assert "agents:run" in ROLE_PERMISSIONS_MAP["ADMIN"]
    assert "agents:run" not in ROLE_PERMISSIONS_MAP["READ"]


def test_unauthenticated_request() -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Bearer access token required"


def test_invalid_jwt() -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid-jwt-token-string"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired access token"


def test_wrong_issuer() -> None:
    token = issue_demo_token(issuer="https://wrong-issuer.com")
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired access token"


def test_wrong_audience() -> None:
    token = issue_demo_token(audience="wrong-audience")
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired access token"


def test_missing_tenant() -> None:
    token = issue_demo_token(tenant_id="")
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Token lacks tenant context"


def test_unauthorized_role() -> None:
    principal = Principal(
        subject="user-1",
        tenant_id="tenant-1",
        roles=frozenset(["viewer"]),
        permissions=frozenset(["read:incidents"]),
    )
    dep = require_role("admin")
    with pytest.raises(HTTPException) as exc_info:
        dep(principal)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Role forbidden"


def test_wrong_tenant_scope_enforcement() -> None:
    principal = Principal(
        subject="user-1",
        tenant_id="tenant-alpha",
        roles=frozenset(["operator"]),
        permissions=frozenset(["read:incidents"]),
    )
    with pytest.raises(HTTPException) as exc_info:
        verify_tenant_scope(principal, target_tenant_id="tenant-beta")
    assert exc_info.value.status_code == 403
    assert "cross-tenant access is forbidden" in exc_info.value.detail


def test_valid_tenant_and_permission() -> None:
    token = issue_demo_token(
        subject="valid-user",
        tenant_id="tenant-100",
        roles=("operator",),
        permissions=("read:incidents", "write:remediation"),
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["subject"] == "valid-user"
    assert data["tenant_id"] == "tenant-100"
    assert "read:incidents" in data["permissions"]

    # Verify permission dependency works cleanly
    principal = Principal(
        subject="valid-user",
        tenant_id="tenant-100",
        roles=frozenset(["operator"]),
        permissions=frozenset(["read:incidents", "write:remediation"]),
    )
    perm_dep = require_permission("read:incidents")
    resolved = perm_dep(principal)
    assert resolved.subject == "valid-user"


def test_demo_token_can_access_current_user() -> None:
    token_response = client.post("/api/v1/auth/demo-token")
    assert token_response.status_code == 200
    assert token_response.json()["read_only_demo"] is True

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_response.json()['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["subject"] == "demo-user"
    assert response.json()["tenant_id"] == "demo-tenant"
    assert response.json()["read_only_demo"] is True
    assert response.json()["roles"] == ["READ"]

    mutation = client.post(
        "/api/v1/organizations",
        json={"name": "Must Not Be Created"},
        headers={"Authorization": f"Bearer {token_response.json()['access_token']}"},
    )
    assert mutation.status_code == 403
    assert mutation.json()["code"] == "demo_read_only"


def test_demo_token_cannot_become_writable_after_context_switch() -> None:
    token = client.post("/api/v1/auth/demo-token").json()["access_token"]
    response = client.post(
        "/api/v1/auth/switch-context",
        json={"organization_id": "demo-tenant"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in (401, 403, 404)


def test_project_and_environment_admin_roles_do_not_grant_tenant_admin_permissions() -> None:
    project_admin = Principal(
        subject="project-admin",
        tenant_id="tenant-1",
        roles=frozenset({"PROJECT_ADMIN"}),
        permissions=frozenset(ROLE_PERMISSIONS_MAP["PROJECT_ADMIN"]),
        project_id="project-1",
    )
    assert "project:update" in project_admin.permissions
    assert "organization:delete" not in project_admin.permissions
    assert "approvals:approve" not in project_admin.permissions
    assert "member:remove" not in project_admin.permissions

    with pytest.raises(HTTPException) as exc_info:
        require_permission("approvals:approve")(project_admin)
    assert exc_info.value.status_code == 403


def test_production_cannot_enable_demo_mode() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", demo_mode=True)


def test_keycloak_login_rejects_unverified_or_mismatched_email() -> None:
    token = issue_demo_token(
        subject="idp-subject",
        tenant_id="tenant-1",
        email="verified@example.com",
        email_verified=True,
    )
    response = client.post(
        "/api/v1/auth/keycloak-login",
        json={"subject": "idp-subject", "email": "other@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "verified identity" in response.json()["detail"]


def test_password_reset_endpoints_report_unimplemented() -> None:
    forgot = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "person@example.com"},
    )
    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "reset-token", "new_password": "long-enough-password"},
    )

    assert forgot.status_code == 501
    assert "not configured" in forgot.json()["detail"].lower()
    assert reset.status_code == 501
    assert "not configured" in reset.json()["detail"].lower()


def test_production_rejects_default_jwt_secret() -> None:
    try:
        Settings(app_env="production", demo_mode=False)
    except ValidationError:
        return
    raise AssertionError("Production settings must reject the local JWT secret")
