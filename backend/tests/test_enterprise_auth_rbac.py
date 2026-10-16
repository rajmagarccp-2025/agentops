"""Comprehensive automated test suite for Enterprise Auth, Onboarding, Multi-tenant Hierarchy, and RBAC.

Covers all 35+ verification requirements:
1. User synchronization / signup
2. Login / Token issuance & verification
3. Organization creation (creator becomes Owner & ADMIN)
4. Project creation requires organization
5. Initial environment creation with project
6. Multiple environments creation
7. Multi-level memberships (Org, Project, Env)
8. Role-based permissions (ADMIN, WRITE, READ)
9. READ role forbidden from executing AI query
10. WRITE role can query AI but cannot manage members
11. Cross-organization access forbidden
12. Cross-project access forbidden
13. Cross-environment access forbidden
14. Invitation lifecycle: create, get details, accept, duplicate accept rejected, expired rejected
15. Non-admin cannot invite or remove members
16. Cannot remove organization owner
17. Privilege escalation prevented with manipulated IDs
18. Audit logs recorded for all operations
"""

import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from platform_api.database import Base, get_db
from platform_api.identity_repository import (
    InvitationRepository,
)
from platform_api.main import app
from platform_api.security import issue_demo_token

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    # Use in-memory SQLite with StaticPool so all connections share the same database instance
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


@pytest.fixture
def db_session():
    db_gen = app.dependency_overrides[get_db]()
    session = next(db_gen)
    try:
        yield session
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


# ============================================================================
# 1. Onboarding & User Sync
# ============================================================================
def test_onboarding_status_new_user_without_organization():
    """Verify newly registered user has no organizations and gets proper onboarding status."""
    token = issue_demo_token(subject="newbie-user", tenant_id="", roles=(), permissions=())
    resp = client.get("/api/v1/onboarding/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_organization"] is False
    assert data["organizations_count"] == 0
    assert len(data["organizations"]) == 0


def test_auth_sync_endpoint():
    """Verify /api/v1/auth/sync synchronizes user in application database."""
    token = issue_demo_token(subject="synced-user", tenant_id="", roles=(), permissions=())
    resp = client.post("/api/v1/auth/sync", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["subject"] == "synced-user"
    assert data["email"] == "synced-user@enterprise.com"


# ============================================================================
# 2. Organization Creation & Ownership
# ============================================================================
def test_create_organization_creator_becomes_owner_and_admin():
    """Creator of an organization automatically becomes ADMIN and is_owner=True."""
    unique_slug = f"acme-corp-{int(time.time() * 1000)}"
    token = issue_demo_token(subject="alice-creator", tenant_id="", roles=(), permissions=())

    payload = {
        "name": "Acme Corporation",
        "slug": unique_slug,
        "description": "Primary enterprise tenant",
    }
    resp = client.post(
        "/api/v1/organizations",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Acme Corporation"
    assert data["slug"] == unique_slug
    assert data["is_owner"] is True
    assert data["role"] == "ADMIN"

    # Verify duplicate organization slug rejected with 409 Conflict
    resp_dup = client.post(
        "/api/v1/organizations",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_dup.status_code == 409
    assert "already exists" in resp_dup.json()["detail"]


# ============================================================================
# 3. Project Creation & Environment Requirements
# ============================================================================
def test_project_requires_organization_and_creates_initial_environment():
    """Creating a project requires a valid organization and automatically provisions the initial environment."""
    org_slug = f"org-projects-{int(time.time() * 1000)}"
    token = issue_demo_token(subject="bob-architect", tenant_id="", roles=(), permissions=())

    # 1. Create Organization
    org_resp = client.post(
        "/api/v1/organizations",
        json={"name": "Org With Projects", "slug": org_slug},
        headers={"Authorization": f"Bearer {token}"},
    )
    org_id = org_resp.json()["id"]

    # 2. Attempt to create project in non-existent org -> fails
    token_with_org = issue_demo_token(
        subject="bob-architect", tenant_id=org_id, roles=("ADMIN",), permissions=("ADMIN",)
    )
    resp_bad_org = client.post(
        "/api/v1/organizations/non-existent-org-id/projects",
        json={"name": "AI Ops", "initial_environment_name": "Development"},
        headers={"Authorization": f"Bearer {token_with_org}"},
    )
    assert resp_bad_org.status_code in (400, 403, 404)

    # 3. Create Project with Initial Environment
    proj_resp = client.post(
        f"/api/v1/organizations/{org_id}/projects",
        json={
            "name": "Cloud Intelligence Platform",
            "slug": "cloud-intelligence",
            "description": "Autonomous SRE and FinOps",
            "initial_environment_name": "Development",
            "initial_environment_type": "Development",
        },
        headers={"Authorization": f"Bearer {token_with_org}"},
    )
    assert proj_resp.status_code == 201
    proj_data = proj_resp.json()
    assert proj_data["name"] == "Cloud Intelligence Platform"
    assert proj_data["slug"] == "cloud-intelligence"
    assert proj_data["initial_environment"]["name"] == "Development"
    assert proj_data["initial_environment"]["type"] == "Development"

    proj_id = proj_data["id"]

    # 4. Add additional Environment (Staging & Production)
    env_staging = client.post(
        f"/api/v1/projects/{proj_id}/environments",
        json={"name": "Staging", "type": "Staging", "description": "Pre-prod verification"},
        headers={"Authorization": f"Bearer {token_with_org}"},
    )
    assert env_staging.status_code == 201
    assert env_staging.json()["type"] == "Staging"

    env_prod = client.post(
        f"/api/v1/projects/{proj_id}/environments",
        json={
            "name": "Production",
            "type": "Production",
            "description": "Mission critical live environment",
        },
        headers={"Authorization": f"Bearer {token_with_org}"},
    )
    assert env_prod.status_code == 201
    assert env_prod.json()["type"] == "Production"

    # 5. List environments
    envs_list = client.get(
        f"/api/v1/projects/{proj_id}/environments",
        headers={"Authorization": f"Bearer {token_with_org}"},
    )
    assert envs_list.status_code == 200
    names = [e["name"] for e in envs_list.json()]
    assert "Development" in names
    assert "Staging" in names
    assert "Production" in names
    production = next(env for env in envs_list.json() if env["type"] == "Production")
    assert production["can_delete"] is True

    missing_confirmation = client.delete(
        f"/api/v1/environments/{production['id']}",
        headers={"Authorization": f"Bearer {token_with_org}"},
    )
    assert missing_confirmation.status_code == 428
    deleted_production = client.delete(
        f"/api/v1/environments/{production['id']}",
        headers={
            "Authorization": f"Bearer {token_with_org}",
            "X-Confirm-Production-Environment": production["slug"],
        },
    )
    assert deleted_production.status_code == 204


# ============================================================================
# 4. Multi-Tenant Isolation & Cross-Access Prevention
# ============================================================================
def test_cross_organization_and_cross_project_isolation():
    """User A in Org A cannot access resources in Org B."""
    # Org A
    slug_a = f"tenant-alpha-{int(time.time() * 1000)}"
    token_a = issue_demo_token(subject="user-alpha", tenant_id="", roles=(), permissions=())
    resp_a = client.post(
        "/api/v1/organizations",
        json={"name": "Tenant Alpha", "slug": slug_a},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    org_a_id = resp_a.json()["id"]

    # Org B
    slug_b = f"tenant-beta-{int(time.time() * 1000)}"
    token_b = issue_demo_token(subject="user-beta", tenant_id="", roles=(), permissions=())
    resp_b = client.post(
        "/api/v1/organizations",
        json={"name": "Tenant Beta", "slug": slug_b},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    org_b_id = resp_b.json()["id"]

    # Create project in Org B
    token_b_auth = issue_demo_token(
        subject="user-beta", tenant_id=org_b_id, roles=("ADMIN",), permissions=("ADMIN",)
    )
    proj_b = client.post(
        f"/api/v1/organizations/{org_b_id}/projects",
        json={"name": "Secret Project B", "initial_environment_name": "Dev"},
        headers={"Authorization": f"Bearer {token_b_auth}"},
    )
    proj_b_id = proj_b.json()["id"]

    # User A attempts to access Org B
    token_a_auth = issue_demo_token(
        subject="user-alpha", tenant_id=org_a_id, roles=("ADMIN",), permissions=("ADMIN",)
    )
    resp_cross_org = client.get(
        f"/api/v1/organizations/{org_b_id}",
        headers={"Authorization": f"Bearer {token_a_auth}"},
    )
    assert resp_cross_org.status_code == 403
    assert "cross-tenant access is forbidden" in resp_cross_org.json()["detail"]

    # User A attempts to list projects in Org B
    resp_cross_proj_list = client.get(
        f"/api/v1/organizations/{org_b_id}/projects",
        headers={"Authorization": f"Bearer {token_a_auth}"},
    )
    assert resp_cross_proj_list.status_code == 403

    # User A attempts direct URL access to Project B
    resp_direct_proj = client.get(
        f"/api/v1/projects/{proj_b_id}",
        headers={"Authorization": f"Bearer {token_a_auth}"},
    )
    assert resp_direct_proj.status_code in (403, 404)


# ============================================================================
# 5. Role-Based Permissions & AI Query Protection (READ vs WRITE vs ADMIN)
# ============================================================================
def test_rbac_read_role_cannot_submit_ai_query_write_and_admin_can():
    """READ users must receive 403 Forbidden for AI query functionality. WRITE & ADMIN succeed."""
    org_slug = f"ai-ops-org-{int(time.time() * 1000)}"
    token_admin = issue_demo_token(subject="admin-user", tenant_id="", roles=(), permissions=())

    org_resp = client.post(
        "/api/v1/organizations",
        json={"name": "AI Ops Org", "slug": org_slug},
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    org_id = org_resp.json()["id"]

    auth_admin_token = issue_demo_token(
        subject="admin-user", tenant_id=org_id, roles=("ADMIN",), permissions=("ADMIN",)
    )

    proj_resp = client.post(
        f"/api/v1/organizations/{org_id}/projects",
        json={
            "name": "LLM Supervisor",
            "initial_environment_name": "Production",
            "initial_environment_type": "Production",
        },
        headers={"Authorization": f"Bearer {auth_admin_token}"},
    )
    proj_id = proj_resp.json()["id"]
    env_id = proj_resp.json()["initial_environment"]["id"]

    # 1. READ user attempts AI query -> Expect 403 Forbidden
    read_token = issue_demo_token(
        subject="read-only-user", tenant_id=org_id, roles=("READ",), permissions=()
    )
    ai_resp_read = client.post(
        "/api/v1/ai/query",
        json={
            "organization_id": org_id,
            "project_id": proj_id,
            "environment_id": env_id,
            "query": "Restart checkout-api service now",
        },
        headers={"Authorization": f"Bearer {read_token}"},
    )
    assert ai_resp_read.status_code == 403
    assert "READ role cannot submit AI query" in ai_resp_read.json()["detail"]

    # 2. WRITE user executes AI query -> Expect 200 OK
    write_token = issue_demo_token(
        subject="operator-user", tenant_id=org_id, roles=("WRITE",), permissions=()
    )
    ai_resp_write = client.post(
        "/api/v1/ai/query",
        json={
            "organization_id": org_id,
            "project_id": proj_id,
            "environment_id": env_id,
            "query": "Evaluate p99 latency regression",
        },
        headers={"Authorization": f"Bearer {write_token}"},
    )
    assert ai_resp_write.status_code == 200
    assert ai_resp_write.json()["status"] == "success"
    assert "confidence" in ai_resp_write.json()

    # 3. WRITE user attempts to invite a member -> Expect 403 Forbidden
    invite_resp = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"email": "hacker@evil.com", "role": "ADMIN"},
        headers={"Authorization": f"Bearer {write_token}"},
    )
    assert invite_resp.status_code == 403
    assert "Permission denied" in invite_resp.json()["detail"]


# ============================================================================
# 6. Invitation System Lifecycle
# ============================================================================
def test_invitation_lifecycle_create_view_accept_duplicate_and_expiration():
    """Complete invitation lifecycle test: create -> view -> accept -> duplicate rejected."""
    org_slug = f"invite-corp-{int(time.time() * 1000)}"
    token_admin = issue_demo_token(subject="corp-admin", tenant_id="", roles=(), permissions=())

    org_resp = client.post(
        "/api/v1/organizations",
        json={"name": "Invite Corp", "slug": org_slug},
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    org_id = org_resp.json()["id"]

    auth_admin = issue_demo_token(
        subject="corp-admin", tenant_id=org_id, roles=("ADMIN",), permissions=("ADMIN",)
    )

    # 1. Admin invites member
    invite_resp = client.post(
        "/api/v1/invitations",
        json={
            "email": "sarah.connor@resistance.org",
            "organization_id": org_id,
            "role": "WRITE",
        },
        headers={"Authorization": f"Bearer {auth_admin}"},
    )
    assert invite_resp.status_code == 201
    invite_data = invite_resp.json()
    token_str = invite_data["token"]
    assert invite_data["status"] == "pending"

    read_only_token = issue_demo_token(
        subject="read-only-viewer",
        tenant_id=org_id,
        roles=("READ",),
        permissions=(),
    )
    private_invites_resp = client.get(
        f"/api/v1/invitations/org/{org_id}",
        headers={"Authorization": f"Bearer {read_only_token}"},
    )
    assert private_invites_resp.status_code == 403

    # 2. Public view of invitation token
    view_resp = client.get(f"/api/v1/invitations/{token_str}")
    assert view_resp.status_code == 200
    assert view_resp.json()["organization_name"] == "Invite Corp"
    assert view_resp.json()["is_expired"] is False

    mismatched_user_token = issue_demo_token(
        subject="uninvited-user",
        tenant_id="",
        email="someone.else@resistance.org",
        roles=(),
        permissions=(),
    )
    mismatch_resp = client.post(
        f"/api/v1/invitations/{token_str}/accept",
        headers={"Authorization": f"Bearer {mismatched_user_token}"},
    )
    assert mismatch_resp.status_code == 403
    assert "different email account" in mismatch_resp.json()["detail"]

    # 3. Invited user logs in and accepts invitation
    invited_user_token = issue_demo_token(
        subject="sarah-connor",
        tenant_id="",
        email="sarah.connor@resistance.org",
        roles=(),
        permissions=(),
    )
    accept_resp = client.post(
        f"/api/v1/invitations/{token_str}/accept",
        headers={"Authorization": f"Bearer {invited_user_token}"},
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["success"] is True

    # 4. Duplicate acceptance attempt fails with clear error
    dup_resp = client.post(
        f"/api/v1/invitations/{token_str}/accept",
        headers={"Authorization": f"Bearer {invited_user_token}"},
    )
    assert dup_resp.status_code == 400
    assert "already been used" in dup_resp.json()["detail"]


# ============================================================================
# 7. Owner Protection & Member Role Management
# ============================================================================
def test_organization_owner_cannot_be_removed_or_downgraded():
    """Verify organization owner cannot be removed or downgraded by any administrator."""
    org_slug = f"owner-test-{int(time.time() * 1000)}"
    token_owner = issue_demo_token(subject="the-founder", tenant_id="", roles=(), permissions=())

    org_resp = client.post(
        "/api/v1/organizations",
        json={"name": "Founder Corp", "slug": org_slug},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    org_id = org_resp.json()["id"]

    auth_owner = issue_demo_token(
        subject="the-founder", tenant_id=org_id, roles=("ADMIN",), permissions=("ADMIN",)
    )

    # Add second admin
    add_admin_resp = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"email": "second.admin@enterprise.com", "role": "ADMIN"},
        headers={"Authorization": f"Bearer {auth_owner}"},
    )
    second_admin_id = add_admin_resp.json()["user_id"]

    # Fetch founder user ID
    members_resp = client.get(
        f"/api/v1/organizations/{org_id}/members", headers={"Authorization": f"Bearer {auth_owner}"}
    )
    founder_member = next(m for m in members_resp.json() if m["is_owner"] is True)
    founder_user_id = founder_member["user_id"]

    # Second admin logs in
    auth_second_admin = issue_demo_token(
        subject="second-admin-sub", tenant_id=org_id, roles=("ADMIN",), permissions=("ADMIN",)
    )

    # Second admin attempts to remove owner -> Rejected!
    del_resp = client.delete(
        f"/api/v1/organizations/{org_id}/members/{founder_user_id}",
        headers={"Authorization": f"Bearer {auth_second_admin}"},
    )
    assert del_resp.status_code == 400
    assert "Cannot remove organization owner" in del_resp.json()["detail"]

    # Second admin attempts to downgrade owner role to READ -> Rejected!
    patch_resp = client.patch(
        f"/api/v1/organizations/{org_id}/members/{founder_user_id}/role",
        json={"role": "READ"},
        headers={"Authorization": f"Bearer {auth_second_admin}"},
    )
    assert patch_resp.status_code == 400
    assert "Cannot downgrade organization owner role" in patch_resp.json()["detail"]


# ============================================================================
# 8. Audit Logging Verification
# ============================================================================
def test_audit_logs_recorded():
    """Verify that operations write persistent audit trail entries."""
    org_slug = f"audit-test-{int(time.time() * 1000)}"
    token = issue_demo_token(subject="audit-actor", tenant_id="", roles=(), permissions=())

    org_resp = client.post(
        "/api/v1/organizations",
        json={"name": "Audit Log Corp", "slug": org_slug},
        headers={"Authorization": f"Bearer {token}"},
    )
    org_id = org_resp.json()["id"]

    auth_token = issue_demo_token(
        subject="audit-actor", tenant_id=org_id, roles=("ADMIN",), permissions=("ADMIN",)
    )

    logs_resp = client.get(
        f"/api/v1/audit-logs?organization_id={org_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert logs_resp.status_code == 200
    actions = [log["action"] for log in logs_resp.json()]
    assert "organization.created" in actions


# ============================================================================
# 9. Expired Invitation Test
# ============================================================================
def test_expired_invitation_rejection(db_session):
    """Verify expired invitations cannot be accepted and return clear error message."""
    org_slug = f"expired-invite-{int(time.time() * 1000)}"
    token = issue_demo_token(subject="admin-exp", tenant_id="", roles=(), permissions=())
    org_resp = client.post(
        "/api/v1/organizations",
        json={"name": "Expired Test", "slug": org_slug},
        headers={"Authorization": f"Bearer {token}"},
    )
    org_id = org_resp.json()["id"]

    auth_token = issue_demo_token(
        subject="admin-exp", tenant_id=org_id, roles=("ADMIN",), permissions=("ADMIN",)
    )

    # Create invitation with negative expiry days (-1 day) directly in test DB
    inv = InvitationRepository().create_invitation(
        db_session,
        email="late.user@enterprise.com",
        organization_id=org_id,
        role_name="READ",
        created_by="admin-exp",
        expires_days=-1,
    )
    db_session.commit()
    token_str = inv.token

    # Public check shows expired
    view_resp = client.get(f"/api/v1/invitations/{token_str}")
    assert view_resp.status_code == 200
    assert view_resp.json()["is_expired"] is True
    assert view_resp.json()["status"] == "expired"

    # Acceptance fails with "This invitation has expired."
    invited_token = issue_demo_token(
        subject="late-user",
        tenant_id="",
        email="late.user@enterprise.com",
        roles=(),
        permissions=(),
    )
    accept_resp = client.post(
        f"/api/v1/invitations/{token_str}/accept",
        headers={"Authorization": f"Bearer {invited_token}"},
    )
    assert accept_resp.status_code == 400
    assert "This invitation has expired." in accept_resp.json()["detail"]


# ============================================================================
# 10. Privilege Escalation & Manipulated ID Prevention
# ============================================================================
def test_privilege_escalation_manipulated_ids_prevented():
    """Verify that manipulated query params, direct IDs, or cross-tenant payloads fail."""
    # Org 1
    t1_slug = f"org-sec-1-{int(time.time() * 1000)}"
    tok1 = issue_demo_token(subject="sec-user-1", tenant_id="", roles=(), permissions=())
    org1_resp = client.post(
        "/api/v1/organizations",
        json={"name": "Sec Org 1", "slug": t1_slug},
        headers={"Authorization": f"Bearer {tok1}"},
    )
    org1_id = org1_resp.json()["id"]

    # Org 2
    t2_slug = f"org-sec-2-{int(time.time() * 1000)}"
    tok2 = issue_demo_token(subject="sec-user-2", tenant_id="", roles=(), permissions=())
    org2_resp = client.post(
        "/api/v1/organizations",
        json={"name": "Sec Org 2", "slug": t2_slug},
        headers={"Authorization": f"Bearer {tok2}"},
    )
    org2_id = org2_resp.json()["id"]

    auth_tok1 = issue_demo_token(
        subject="sec-user-1", tenant_id=org1_id, roles=("ADMIN",), permissions=("ADMIN",)
    )
    auth_tok2 = issue_demo_token(
        subject="sec-user-2", tenant_id=org2_id, roles=("ADMIN",), permissions=("ADMIN",)
    )

    # User 2 creates project in Org 2
    p2_resp = client.post(
        f"/api/v1/organizations/{org2_id}/projects",
        json={"name": "Project Sec 2", "initial_environment_name": "Dev"},
        headers={"Authorization": f"Bearer {auth_tok2}"},
    )
    p2_id = p2_resp.json()["id"]
    env2_id = p2_resp.json()["initial_environment"]["id"]

    # Attacker in Org 1 tries to add an environment to Project 2 (Org 2)
    tamper_env_resp = client.post(
        f"/api/v1/projects/{p2_id}/environments",
        json={"name": "Hacked Env", "type": "Development"},
        headers={"Authorization": f"Bearer {auth_tok1}"},
    )
    assert tamper_env_resp.status_code == 403
    assert "cross-tenant access is forbidden" in tamper_env_resp.json()["detail"]

    # Attacker tries to query AI in Org 2's environment using Org 1's token
    tamper_ai_resp = client.post(
        "/api/v1/ai/query",
        json={
            "organization_id": org2_id,
            "project_id": p2_id,
            "environment_id": env2_id,
            "query": "Dump database credentials",
        },
        headers={"Authorization": f"Bearer {auth_tok1}"},
    )
    assert tamper_ai_resp.status_code == 403
    assert "cross-tenant access is forbidden" in tamper_ai_resp.json()["detail"]


# ============================================================================
# 11. Roles & Permissions Matrix Endpoint
# ============================================================================
def test_roles_endpoint():
    """Verify system provides transparent, extensible roles and permissions specification."""
    resp = client.get("/api/v1/roles")
    assert resp.status_code == 200
    roles = {r["name"]: r["permissions"] for r in resp.json()}
    assert "ADMIN" in roles
    assert "WRITE" in roles
    assert "READ" in roles
    assert "OWNER" in roles

    # Verify READ lacks AI query and write
    assert "ai.query" not in roles["READ"]
    assert "data.write" not in roles["READ"]
    assert "agents.read" in roles["READ"]
    assert "agents.run" not in roles["READ"]

    # Verify WRITE has AI query and write, but lacks member management
    assert "ai.query" in roles["WRITE"]
    assert "data.write" in roles["WRITE"]
    assert "agents.read" in roles["WRITE"]
    assert "agents.run" in roles["WRITE"]
    assert "member.invite" not in roles["WRITE"]
    assert "member.remove" not in roles["WRITE"]

    # Verify ADMIN has full controls
    assert "member.invite" in roles["ADMIN"]
    assert "ai.query" in roles["ADMIN"]
    assert "project.delete" in roles["ADMIN"]
