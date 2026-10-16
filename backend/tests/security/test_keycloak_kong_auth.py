"""Automated Test Suite for Keycloak, OIDC PKCE, Kong, and FastAPI Authentication & Tenancy.

Covers all 14 mandatory validation test cases:
1. Login succeeds
2. Invalid credentials fail
3. Invalid redirect fails
4. Missing token fails
5. Expired token fails
6. Wrong issuer fails
7. Wrong audience fails
8. Invalid signature fails
9. Logout works
10. Protected API without authentication returns 401
11. Authenticated user without permission returns 403
12. User cannot select an unauthorized tenant
13. User cannot select an unauthorized environment
14. User cannot modify tenant ID to access another tenant
"""

import json
from pathlib import Path
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from platform_api.config import get_settings
from platform_api.main import app
from platform_api.security import (
    Principal,
    verify_tenant_scope,
)


@pytest.fixture(scope="module")
def rsa_keypair():
    """Generate ephemeral RSA 2048 keypair for Keycloak token simulation."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


@pytest.fixture
def client(rsa_keypair):
    """Test client configured with OIDC RSA public key."""
    _, public_pem = rsa_keypair
    settings = get_settings()
    original_public_key = settings.oidc_public_key
    original_issuer = settings.oidc_issuer_url
    original_audience = settings.oidc_audience

    settings.oidc_public_key = public_pem
    settings.oidc_issuer_url = "http://localhost:8080/realms/platform"
    settings.oidc_audience = "agentic-platform-api"

    with TestClient(app) as tc:
        yield tc

    settings.oidc_public_key = original_public_key
    settings.oidc_issuer_url = original_issuer
    settings.oidc_audience = original_audience


def make_keycloak_token(
    rsa_keypair,
    sub: str = "alex.rivera",
    tenant_id: str = "northstar-production",
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
    tenant_memberships: list[dict[str, Any]] | None = None,
    issuer: str = "http://localhost:8080/realms/platform",
    audience: str = "agentic-platform-api",
    expires_in_seconds: int = 1800,
    issued_at_delta: int = 0,
) -> str:
    private_pem, _ = rsa_keypair
    now = int(time.time()) + issued_at_delta
    roles_list = roles if roles is not None else ["platform-admin", "operator"]
    perms_list = (
        permissions
        if permissions is not None
        else [
            "inventory.read",
            "incident.read",
            "security.read",
            "finops.read",
            "llmops.read",
            "rag.read",
            "rag.manage",
            "workflow.execute",
            "remediation.request",
            "remediation.approve",
            "governance.manage",
            "audit.read",
        ]
    )
    memberships = (
        tenant_memberships
        if tenant_memberships is not None
        else [
            {"tenant_id": "northstar-production", "roles": ["platform-admin", "operator"]},
            {"tenant_id": "fintech-staging", "roles": ["operator"]},
        ]
    )

    claims = {
        "sub": sub,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + expires_in_seconds,
        "azp": "platform-frontend",
        "session_id": "sess-xyz-987",
        "auth_time": now,
        "realm_access": {"roles": roles_list},
        "roles": roles_list,
        "permissions": perms_list,
        "tenant_id": tenant_id,
        "tenant_memberships": memberships,
    }
    return jwt.encode(claims, private_pem, algorithm="RS256")


# ============================================================================
# 1. Login succeeds
# ============================================================================
def test_1_login_succeeds(client, rsa_keypair):
    """Test that a valid Keycloak token is accepted and yields full trusted principal context."""
    token = make_keycloak_token(rsa_keypair)
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["subject"] == "alex.rivera"
    assert data["tenant_id"] == "northstar-production"
    assert "platform-admin" in data["roles"]
    assert "inventory.read" in data["permissions"]
    assert "inventory:read" in data["permissions"]  # Canonical bi-directional mapping
    assert data["issuer"] == "http://localhost:8080/realms/platform"
    assert data["session_id"] == "sess-xyz-987"
    assert len(data["tenant_memberships"]) == 2


# ============================================================================
# 2. Invalid credentials fail
# ============================================================================
def test_2_invalid_credentials_fail(client):
    """Test that attempting authentication with invalid credentials / tokens fails with 401."""
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bad-token-format"})
    assert response.status_code == 401
    assert "Invalid or expired" in response.json()["detail"]


# ============================================================================
# 3. Invalid redirect fails
# ============================================================================
def test_3_invalid_redirect_fails():
    """Verify Keycloak realm specification prevents invalid/open redirect URIs."""
    repo_root = Path(__file__).resolve().parents[3]
    realm_config_path = repo_root / "deployment" / "keycloak" / "realm-export.json"
    if not realm_config_path.exists():
        realm_config_path = Path("deployment/keycloak/realm-export.json")
    with open(realm_config_path, encoding="utf-8") as f:
        config = json.load(f)

    frontend_client = next(c for c in config["clients"] if c["clientId"] == "platform-frontend")
    redirect_uris = frontend_client["redirectUris"]

    # Allowed redirects are strictly constrained to application domain
    for uri in redirect_uris:
        assert uri.startswith("http://localhost:3000")

    # Malicious redirect URIs must NOT be present
    malicious_redirect = "http://evil-attacker.com/oauth/callback"
    assert malicious_redirect not in redirect_uris


# ============================================================================
# 4. Missing token fails
# ============================================================================
def test_4_missing_token_fails(client):
    """Test that protected endpoints fail with 401 when Authorization header is omitted."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "Bearer access token required" in response.json()["detail"]


# ============================================================================
# 5. Expired token fails
# ============================================================================
def test_5_expired_token_fails(client, rsa_keypair):
    """Test that tokens with exp in the past are rejected with 401."""
    # Token expired 60 seconds ago
    token = make_keycloak_token(rsa_keypair, expires_in_seconds=-60, issued_at_delta=-120)
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "Invalid or expired" in response.json()["detail"]


# ============================================================================
# 6. Wrong issuer fails
# ============================================================================
def test_6_wrong_issuer_fails(client, rsa_keypair):
    """Test that tokens from untrusted / spoofed issuers are rejected with 401."""
    token = make_keycloak_token(rsa_keypair, issuer="http://rogue-idp.attacker.com/realms/platform")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "Invalid or expired" in response.json()["detail"]


# ============================================================================
# 7. Wrong audience fails
# ============================================================================
def test_7_wrong_audience_fails(client, rsa_keypair):
    """Test that tokens issued for another audience/resource are rejected with 401."""
    token = make_keycloak_token(rsa_keypair, audience="some-other-unrelated-api")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "Invalid or expired" in response.json()["detail"]


# ============================================================================
# 8. Invalid signature fails
# ============================================================================
def test_8_invalid_signature_fails(client):
    """Test that tokens signed with a different/untrusted private key fail signature verification."""
    # Generate an untrusted rogue key
    rogue_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rogue_pem = rogue_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    now = int(time.time())
    claims = {
        "sub": "attacker",
        "iss": "http://localhost:8080/realms/platform",
        "aud": "agentic-platform-api",
        "iat": now,
        "exp": now + 1800,
        "tenant_id": "northstar-production",
        "roles": ["platform-admin"],
    }
    untrusted_token = jwt.encode(claims, rogue_pem, algorithm="RS256")

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {untrusted_token}"})
    assert response.status_code == 401
    assert "Invalid or expired" in response.json()["detail"]


# ============================================================================
# 9. Logout works
# ============================================================================
def test_9_logout_works():
    """Verify that logout clears sessions and redirects to Keycloak end-session."""
    # Verify logout implementation in Next.js BFF route
    repo_root = Path(__file__).resolve().parents[3]
    logout_route_file = repo_root / "frontend" / "src" / "app" / "api" / "auth" / "logout" / "route.ts"
    if not logout_route_file.exists():
        logout_route_file = Path("frontend/src/app/api/auth/logout/route.ts")
    with open(logout_route_file, encoding="utf-8") as f:
        content = f.read()

    # Ensure required cookies are explicitly deleted upon logout
    expected_cookies = [
        "platform_access_token",
        "platform_refresh_token",
        "platform_session",
        "oidc_code_verifier",
        "oidc_auth_state",
    ]
    for cookie in expected_cookies:
        assert f'response.cookies.delete("{cookie}")' in content

    # Ensure Keycloak OIDC end-session endpoint redirect is generated
    assert "protocol/openid-connect/logout" in content
    assert "post_logout_redirect_uri" in content


# ============================================================================
# 10. Protected API without authentication returns 401
# ============================================================================
def test_10_protected_api_without_auth_returns_401(client):
    """Test various protected operational endpoints return 401 when no token is present."""
    endpoints = [
        "/api/v1/inventory/resources",
        "/api/v1/incidents",
        "/api/v1/finops/summary",
        "/api/v1/llmops/telemetry",
        "/api/v1/approvals",
    ]
    for endpoint in endpoints:
        resp = client.get(endpoint)
        assert resp.status_code == 401, f"Expected 401 for {endpoint}, got {resp.status_code}"


# ============================================================================
# 11. Authenticated user without permission returns 403
# ============================================================================
def test_11_authenticated_user_without_permission_returns_403(client, rsa_keypair):
    """Test that an authenticated user lacking required permission receives 403 Forbidden."""
    # User has only inventory.read permission, no remediation or write permissions
    limited_token = make_keycloak_token(
        rsa_keypair,
        sub="viewer-user",
        roles=["viewer"],
        permissions=["inventory.read"],
    )

    # Attempt to post a remediation action (requires remediation:execute)
    remediation_payload = {
        "incident_id": "inc-001",
        "action": "restart_service",
        "target_resource": "orders-db",
        "parameters": {},
        "risk": "medium",
    }
    resp = client.post(
        "/api/v1/remediation/actions",
        json=remediation_payload,
        headers={"Authorization": f"Bearer {limited_token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Permission denied"


# ============================================================================
# 12. User cannot select an unauthorized tenant
# ============================================================================
def test_12_user_cannot_select_unauthorized_tenant(rsa_keypair):
    """Test that a user cannot access or perform operations on a tenant they do not belong to."""
    # User belongs only to northstar-production
    principal = Principal(
        subject="restricted-user",
        subject_id="restricted-user",
        tenant_id="northstar-production",
        roles=frozenset(["operator"]),
        permissions=frozenset(["incident.read"]),
        tenant_memberships=({"tenant_id": "northstar-production", "roles": ["operator"]},),
    )

    # Verifying target tenant matches
    verify_tenant_scope(principal, "northstar-production")  # Should succeed

    # User attempts to select or act on 'fintech-staging' or 'health-dev'
    with pytest.raises(Exception) as exc_info:
        verify_tenant_scope(principal, "fintech-staging")
    assert "cross-tenant access is forbidden" in str(exc_info.value.detail)


# ============================================================================
# 13. User cannot select an unauthorized environment
# ============================================================================
def test_13_user_cannot_select_unauthorized_environment(rsa_keypair):
    """Test that server-side policy enforces environment boundaries for unauthorized roles."""
    from platform_api.governance.policy import policy_engine
    from platform_api.governance.schemas import ToolRisk

    # User has developer role (only staging access, blocked from critical production mutations)
    developer_principal = Principal(
        subject="dev-user",
        subject_id="dev-user",
        tenant_id="northstar-production",
        roles=frozenset(["developer"]),
        permissions=frozenset(["remediation.request"]),
        tenant_memberships=({"tenant_id": "northstar-production", "roles": ["developer"]},),
    )

    decision = policy_engine.evaluate(
        principal=developer_principal,
        environment="production",
        action="delete",
        risk=ToolRisk.CRITICAL,
        target_tenant_id="northstar-production",
        required_permission="remediation.approve",
    )
    assert decision.allowed is False
    assert "DENIED" in decision.reason


# ============================================================================
# 14. User cannot modify tenant ID to access another tenant
# ============================================================================
def test_14_user_cannot_modify_tenant_id_to_access_another_tenant(client, rsa_keypair):
    """Test that client-supplied tenant ID cannot override server-verified token tenancy."""
    # Attacker token has tenant_id = 'tenant-attacker'
    token = make_keycloak_token(
        rsa_keypair,
        sub="attacker-sub",
        tenant_id="tenant-attacker",
        roles=["operator"],
        permissions=["incidents.read", "incident.read"],
        tenant_memberships=[{"tenant_id": "tenant-attacker", "roles": ["operator"]}],
    )

    # Attacker calls GET /incidents with query parameter or headers claiming to be 'northstar-production'
    resp = client.get(
        "/api/v1/incidents",
        params={"tenant_id": "northstar-production"},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-ID": "northstar-production",
        },
    )
    # The server strictly binds tenant scope to the authenticated token's tenant_id
    assert resp.status_code == 200
    for incident in resp.json():
        # Any incidents returned must strictly belong to the token's authenticated tenant
        assert incident.get("tenant_id") == "tenant-attacker"
