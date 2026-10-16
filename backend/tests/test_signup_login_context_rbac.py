import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from platform_api.database import Base, get_db
from platform_api.main import app

client = TestClient(app)


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


def test_signup_validation_errors():
    """Verify signup validates email format, password matching, and password strength."""
    # 1. Invalid email
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Test User",
            "email": "invalid-email-no-at",
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
    )
    assert resp.status_code == 422

    # 2. Passwords do not match
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Test User",
            "email": "test@example.com",
            "password": "Password123!",
            "confirm_password": "DifferentPassword123!",
        },
    )
    assert resp.status_code == 400
    assert "Passwords do not match" in resp.json()["detail"]

    # 3. Password too short (< 8 chars)
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Test User",
            "email": "test@example.com",
            "password": "Pass1!",
            "confirm_password": "Pass1!",
        },
    )
    assert resp.status_code == 400
    assert "at least 8 characters" in resp.json()["detail"]

    # 4. Weak password without digit or special char
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Test User",
            "email": "test@example.com",
            "password": "WeakPasswordOnlyLetters",
            "confirm_password": "WeakPasswordOnlyLetters",
        },
    )
    assert resp.status_code == 400
    assert "at least one digit or special character" in resp.json()["detail"]


def test_signup_success_and_duplicate_email():
    """Verify successful signup creates user, issues token, and rejects duplicate email."""
    # Successful signup
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Alice Smith",
            "email": "alice@company.com",
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "alice@company.com"
    assert data["user"]["display_name"] == "Alice Smith"
    assert data["user"]["has_organization"] is True

    # Attempt duplicate signup with same email (case-insensitive)
    dup_resp = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Alice Smith Clone",
            "email": "ALICE@company.com",
            "password": "AnotherPassword123!",
            "confirm_password": "AnotherPassword123!",
        },
    )
    assert dup_resp.status_code == 409
    assert "already registered" in dup_resp.json()["detail"]


def test_login_flow():
    """Verify login authentication with valid and invalid credentials."""
    # Create user via signup
    client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Bob Jones",
            "email": "bob@company.com",
            "password": "BobSecretPassword99!",
            "confirm_password": "BobSecretPassword99!",
        },
    )

    # 1. Invalid password
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@company.com", "password": "WrongPassword!"},
    )
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["detail"]

    # 2. Unknown email
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@company.com", "password": "AnyPassword123!"},
    )
    assert resp.status_code == 401

    # 3. Successful login
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@company.com", "password": "BobSecretPassword99!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "bob@company.com"


def test_complete_onboarding_and_context_switching():
    """Verify complete hierarchy flow: Signup -> Create Org -> Create Project -> Create Env -> Switch Context."""
    # 1. Signup
    signup_res = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Carol Danvers",
            "email": "carol@marvel.com",
            "password": "MarvelPassword456!",
            "confirm_password": "MarvelPassword456!",
        },
    )
    assert signup_res.status_code == 201
    token = signup_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create organization (Carol becomes Owner & ADMIN)
    org_res = client.post(
        "/api/v1/organizations",
        json={"name": "Starforce Enterprise", "description": "Primary enterprise org"},
        headers=headers,
    )
    assert org_res.status_code == 201
    org = org_res.json()
    org_id = org["id"]
    assert org["is_owner"] is True
    assert org["role"] == "ADMIN"

    # Refresh token by logging in to acquire org context
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "carol@marvel.com", "password": "MarvelPassword456!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create Project with initial environment
    proj_res = client.post(
        f"/api/v1/organizations/{org_id}/projects",
        json={
            "name": "Defense AI Gateway",
            "description": "Critical autonomous defense",
            "initial_environment_name": "Production",
            "initial_environment_type": "Production",
        },
        headers=headers,
    )
    assert proj_res.status_code == 201
    proj = proj_res.json()
    proj_id = proj["id"]
    env_id = proj["initial_environment"]["id"]

    # 4. Create second environment
    env_res = client.post(
        f"/api/v1/projects/{proj_id}/environments",
        json={
            "name": "Staging",
            "type": "Staging",
            "description": "Pre-production test environment",
        },
        headers=headers,
    )
    assert env_res.status_code == 201
    staging_env_id = env_res.json()["id"]

    # 5. Test switch-context endpoint
    switch_res = client.post(
        "/api/v1/auth/switch-context",
        json={
            "organization_id": org_id,
            "project_id": proj_id,
            "environment_id": staging_env_id,
        },
        headers=headers,
    )
    assert switch_res.status_code == 200
    switch_data = switch_res.json()
    assert switch_data["success"] is True
    assert switch_data["active_context"]["environment_id"] == staging_env_id
    assert switch_data["active_context"]["is_owner"] is True

    # 6. Verify direct API endpoints enforce hierarchy
    # GET /organizations/{org_id}/projects/{proj_id}
    p_get = client.get(
        f"/api/v1/organizations/{org_id}/projects/{proj_id}",
        headers={"Authorization": f"Bearer {switch_data['access_token']}"},
    )
    assert p_get.status_code == 200
    assert p_get.json()["id"] == proj_id

    # GET /projects/{proj_id}/environments/{staging_env_id}
    e_get = client.get(
        f"/api/v1/projects/{proj_id}/environments/{staging_env_id}",
        headers={"Authorization": f"Bearer {switch_data['access_token']}"},
    )
    assert e_get.status_code == 200
    assert e_get.json()["id"] == staging_env_id


def test_tenant_isolation_and_idor_prevention():
    """Verify cross-tenant attacks and manipulated IDs return 403/404."""
    # Create User 1 and Org 1
    client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Org1 User",
            "email": "user1@org1.com",
            "password": "PasswordOrg1!",
            "confirm_password": "PasswordOrg1!",
        },
    )
    login1 = client.post(
        "/api/v1/auth/login", json={"email": "user1@org1.com", "password": "PasswordOrg1!"}
    )
    h1 = {"Authorization": f"Bearer {login1.json()['access_token']}"}
    org1 = client.post("/api/v1/organizations", json={"name": "Org One"}, headers=h1).json()
    # Refresh h1 with tenant context
    login1 = client.post(
        "/api/v1/auth/login", json={"email": "user1@org1.com", "password": "PasswordOrg1!"}
    )
    h1 = {"Authorization": f"Bearer {login1.json()['access_token']}"}
    proj1 = client.post(
        f"/api/v1/organizations/{org1['id']}/projects",
        json={"name": "Project One", "initial_environment_name": "Prod"},
        headers=h1,
    ).json()

    # Create User 2 and Org 2
    client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Org2 User",
            "email": "user2@org2.com",
            "password": "PasswordOrg2!",
            "confirm_password": "PasswordOrg2!",
        },
    )
    login2 = client.post(
        "/api/v1/auth/login", json={"email": "user2@org2.com", "password": "PasswordOrg2!"}
    )
    h2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}
    org2 = client.post("/api/v1/organizations", json={"name": "Org Two"}, headers=h2).json()
    login2 = client.post(
        "/api/v1/auth/login", json={"email": "user2@org2.com", "password": "PasswordOrg2!"}
    )
    h2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

    # Attack 1: User 2 tries to access Org 1
    attack1 = client.get(f"/api/v1/organizations/{org1['id']}", headers=h2)
    assert attack1.status_code in (403, 404)

    # Attack 2: User 2 tries to access Org 1 Project
    attack2 = client.get(f"/api/v1/organizations/{org1['id']}/projects/{proj1['id']}", headers=h2)
    assert attack2.status_code in (403, 404)

    # Attack 3: User 2 tries to switch context to Org 1
    attack3 = client.post(
        "/api/v1/auth/switch-context",
        json={"organization_id": org1["id"]},
        headers=h2,
    )
    assert attack3.status_code in (403, 404)
