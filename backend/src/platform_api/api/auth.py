import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from platform_api.config import get_settings
from platform_api.database import get_db
from platform_api.identity_repository import (
    ROLE_PERMISSIONS_MAP,
    AuditLogRepository,
    EnvironmentRepository,
    MembershipRepository,
    ProjectRepository,
    TenantRepository,
)
from platform_api.security import (
    Principal,
    get_current_principal,
    issue_demo_token,
    issue_user_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    read_only_demo: bool = False


class PrincipalResponse(BaseModel):
    subject: str
    subject_id: str
    tenant_id: str
    tenant_memberships: list[dict[str, Any]]
    roles: list[str]
    permissions: list[str]
    issuer: str | None = None
    audience: str | list[str] | None = None
    authentication_context: dict[str, Any] | None = None
    session_id: str | None = None
    project_id: str | None = None
    environment_id: str | None = None
    is_owner: bool = False
    read_only_demo: bool = False


class SignupRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1)
    confirm_password: str = Field(...)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class SwitchContextRequest(BaseModel):
    organization_id: str = Field(..., min_length=1)
    project_id: str | None = None
    environment_id: str | None = None


class AuthUserResponse(BaseModel):
    id: str
    subject: str
    email: str
    display_name: str
    has_organization: bool
    organizations_count: int
    active_organization_id: str | None = None
    active_project_id: str | None = None
    active_environment_id: str | None = None
    effective_role: str = "READ"
    read_only_demo: bool = False


def _slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"[\s_-]+", "-", s)


def _ensure_default_workspace(db: Session, user: Any) -> tuple[Any, Any, Any]:
    """Ensures the user has at least one organization, project, and environment.
    Creates default workspace if none exists.
    Returns (tenant, project, environment).
    """
    tenants = TenantRepository().list_user_tenants(db, user.id)
    if not tenants:
        base_name = user.display_name.strip() if user.display_name else user.email.split("@")[0]
        org_name = f"{base_name}'s Organization"
        base_slug = _slugify(f"{base_name}-org")
        slug = f"{base_slug}-{user.id[:8]}"

        existing_tenant = TenantRepository().get_tenant_by_slug(db, slug)
        if existing_tenant:
            slug = f"{base_slug}-{user.id[:12]}"

        tenant = TenantRepository().create_tenant(
            db,
            name=org_name,
            slug=slug,
            description="Default workspace created automatically.",
            created_by=user.id,
        )

        MembershipRepository().add_organization_member(
            db,
            tenant_id=tenant.id,
            user_id=user.id,
            role_name="ADMIN",
            is_owner=True,
        )
    else:
        tenant = tenants[0]

    projects = ProjectRepository().list_user_projects(db, tenant.id, user.id, is_org_admin=True)
    if not projects:
        proj_name = "Production AI Platform"
        proj_slug = "production-ai-platform"
        project = ProjectRepository().create_project(
            db,
            tenant_id=tenant.id,
            name=proj_name,
            slug=proj_slug,
            description="Default project created automatically.",
            created_by=user.id,
        )
    else:
        project = projects[0]

    envs = EnvironmentRepository().list_user_environments(
        db, tenant.id, project.id, user.id, is_proj_admin=True
    )
    if not envs:
        env = EnvironmentRepository().create_environment(
            db,
            tenant_id=tenant.id,
            project_id=project.id,
            name="Production",
            slug="production",
            env_type="Production",
            description="Default production environment.",
            created_by=user.id,
        )
    else:
        prod_env = next((e for e in envs if e.type == "Production"), envs[0])
        env = prod_env

    return tenant, project, env


class AuthResultResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthUserResponse


@router.post("/signup", response_model=AuthResultResponse, status_code=status.HTTP_201_CREATED)
@router.post("/register", response_model=AuthResultResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    req: SignupRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResultResponse:
    # 1. Validate email
    clean_email = req.email.lower().strip()
    if not EMAIL_REGEX.match(clean_email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email address format.",
        )

    # 2. Validate password confirmation
    if req.password != req.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match.",
        )

    # 3. Validate password strength
    if len(req.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )
    has_digit_or_special = any(c.isdigit() or not c.isalnum() for c in req.password)
    if not has_digit_or_special:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one digit or special character.",
        )

    # 4. Check for duplicate email
    existing = MembershipRepository().get_user_by_email(db, clean_email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already registered.",
        )

    # 5. Create user and auto-provision default Organization, Project & Environment
    try:
        user = MembershipRepository().create_user_with_password(
            db,
            display_name=req.full_name,
            email=clean_email,
            password=req.password,
        )
        tenant, project, env = _ensure_default_workspace(db, user)
        AuditLogRepository().record_event(
            db,
            actor=user.id,
            actor_email=user.email,
            action="user.signup",
            resource_type="user",
            resource_id=user.id,
            organization_id=tenant.id,
            project_id=project.id,
            environment_id=env.id,
            details={"email": user.email, "display_name": user.display_name},
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create account. Please try again.",
        ) from exc

    settings = get_settings()
    roles_list = ["ADMIN", "OWNER"]
    perms_list = list(ROLE_PERMISSIONS_MAP.get("ADMIN", []))
    tenant_memberships = [{"tenant_id": tenant.id, "roles": roles_list}]

    token = issue_user_token(
        subject=user.subject,
        email=user.email,
        display_name=user.display_name,
        tenant_id=tenant.id,
        roles=roles_list,
        permissions=perms_list,
        tenant_memberships=tenant_memberships,
        project_id=project.id,
        environment_id=env.id,
        is_owner=True,
    )

    return AuthResultResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_demo_token_minutes * 60,
        user=AuthUserResponse(
            id=user.id,
            subject=user.subject,
            email=user.email,
            display_name=user.display_name,
            has_organization=True,
            organizations_count=1,
            active_organization_id=tenant.id,
            active_project_id=project.id,
            active_environment_id=env.id,
            effective_role="ADMIN",
        ),
    )


@router.post("/login", response_model=AuthResultResponse)
async def login(
    req: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResultResponse:
    clean_email = req.email.lower().strip()
    user = MembershipRepository().authenticate_user(db, clean_email, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Determine or auto-provision default workspace if none exists
    tenant, project, env = _ensure_default_workspace(db, user)
    tenants = TenantRepository().list_user_tenants(db, user.id)

    active_org_id = tenant.id
    active_project_id: str | None = project.id if project else None
    active_env_id: str | None = env.id if env else None
    effective_role = "ADMIN"
    is_owner = True

    roles_list: list[str] = []
    perms_list: list[str] = []

    mem_info = MembershipRepository().get_organization_membership(db, tenant.id, user.id)
    if mem_info:
        mem, role = mem_info
        is_owner = mem.is_owner
        effective_role = role.name
        roles_list = [role.name]
        if is_owner:
            roles_list.append("OWNER")
        for r in roles_list:
            perms_list.extend(list(ROLE_PERMISSIONS_MAP.get(r.upper(), [])))

    # Format tenant memberships
    tenant_memberships = MembershipRepository().get_tenant_memberships_for_user(db, user.id)
    if not tenant_memberships:
        tenant_memberships = [{"tenant_id": tenant.id, "roles": roles_list or ["ADMIN"]}]

    settings = get_settings()
    token = issue_user_token(
        subject=user.subject,
        email=user.email,
        display_name=user.display_name,
        tenant_id=active_org_id,
        roles=roles_list,
        permissions=perms_list,
        tenant_memberships=tenant_memberships,
        project_id=active_project_id,
        environment_id=active_env_id,
        is_owner=is_owner,
    )

    AuditLogRepository().record_event(
        db,
        actor=user.id,
        actor_email=user.email,
        action="user.login",
        resource_type="session",
        resource_id=user.id,
        organization_id=active_org_id,
        project_id=active_project_id,
        environment_id=active_env_id,
        details={"email": user.email},
    )
    db.commit()

    return AuthResultResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_demo_token_minutes * 60,
        user=AuthUserResponse(
            id=user.id,
            subject=user.subject,
            email=user.email,
            display_name=user.display_name,
            has_organization=True,
            organizations_count=len(tenants),
            active_organization_id=active_org_id,
            active_project_id=active_project_id,
            active_environment_id=active_env_id,
            effective_role=effective_role,
        ),
    )


@router.post("/switch-context")
async def switch_context(
    req: SwitchContextRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Cryptographically switch the active Organization, Project, and Environment context."""
    user = MembershipRepository().get_user_by_subject(db, principal.subject)
    if not user:
        user = MembershipRepository().get_user_by_email(db, principal.email or "")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    tenant = TenantRepository().get_tenant_by_id(db, req.organization_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    mem_info = MembershipRepository().get_organization_membership(db, tenant.id, user.id)
    is_platform_admin = (
        "platform-admin" in principal.roles or "platform:admin" in principal.permissions
    )
    if not mem_info and not is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this organization.",
        )

    mem, role = mem_info if mem_info else (None, None)
    effective_role = role.name if role else ("ADMIN" if is_platform_admin else "READ")
    role_scope = "organization"
    is_owner = mem.is_owner if mem else False

    project = None
    if req.project_id:
        project = ProjectRepository().get_project_by_id(db, req.project_id)
        if not project or project.tenant_id != tenant.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found in this organization.",
            )
        pm_info = MembershipRepository().get_project_membership(db, project.id, user.id)
        is_org_admin = effective_role in ("ADMIN", "OWNER") or is_platform_admin
        if not pm_info and not is_org_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this project.",
            )
        if pm_info:
            effective_role = pm_info[1].name
            role_scope = "project"

    environment = None
    if req.environment_id:
        if not project:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project context is required when selecting an environment.",
            )
        environment = EnvironmentRepository().get_environment_by_id(db, req.environment_id)
        if (
            not environment
            or environment.project_id != project.id
            or environment.tenant_id != tenant.id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found in this project.",
            )
        em_info = MembershipRepository().get_environment_membership(db, environment.id, user.id)
        is_proj_admin = effective_role in ("ADMIN", "OWNER") or is_platform_admin
        if not em_info and not is_proj_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this environment.",
            )
        if em_info:
            effective_role = em_info[1].name
            role_scope = "environment"

    role_name = effective_role.upper()
    if is_platform_admin:
        token_role = "platform-admin"
    elif role_scope == "project" and role_name in {"ADMIN", "OWNER"}:
        token_role = "PROJECT_ADMIN"
    elif role_scope == "environment" and role_name in {"ADMIN", "OWNER"}:
        token_role = "ENVIRONMENT_ADMIN"
    else:
        token_role = effective_role
    roles_list = [token_role]
    if is_owner and role_scope == "organization":
        roles_list.append("OWNER")
    perms_list: list[str] = []
    for r in roles_list:
        perms_list.extend(list(ROLE_PERMISSIONS_MAP.get(r.upper(), [])))

    tenant_memberships = MembershipRepository().get_tenant_memberships_for_user(db, user.id)

    settings = get_settings()
    new_token = issue_user_token(
        subject=user.subject,
        email=user.email,
        display_name=user.display_name,
        tenant_id=tenant.id,
        roles=roles_list,
        permissions=perms_list,
        tenant_memberships=tenant_memberships,
        project_id=project.id if project else None,
        environment_id=environment.id if environment else None,
        is_owner=is_owner,
        read_only_demo=principal.read_only_demo,
    )

    return {
        "success": True,
        "access_token": new_token,
        "active_context": {
            "organization_id": tenant.id,
            "organization_name": tenant.name,
            "project_id": project.id if project else None,
            "project_name": project.name if project else None,
            "environment_id": environment.id if environment else None,
            "environment_name": environment.name if environment else None,
            "role": effective_role,
            "is_owner": is_owner,
        },
    }


class KeycloakSSOLoginRequest(BaseModel):
    subject: str = Field(..., min_length=1)
    email: str = Field(..., min_length=1)
    full_name: str | None = None
    roles: list[str] = []


@router.post("/keycloak-login", response_model=AuthResultResponse)
async def keycloak_login(
    req: KeycloakSSOLoginRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthResultResponse:
    if principal.subject != req.subject and principal.subject_id != req.subject:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Subject mismatch: authenticated principal does not match request body",
        )
    clean_email = req.email.lower().strip()
    if (
        not principal.email_verified
        or not principal.email
        or principal.email.lower().strip() != clean_email
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The requested email must match the authenticated, verified identity.",
        )
    user = MembershipRepository().get_user_by_subject(db, req.subject)
    if not user:
        user = MembershipRepository().get_user_by_email(db, clean_email)
        if user:
            user.subject = req.subject
            db.commit()

    if not user:
        display_name = req.full_name or clean_email.split("@")[0].replace(".", " ").title()
        user = MembershipRepository().create_user_with_password(
            db,
            display_name=display_name,
            email=clean_email,
            password="",
        )
        user.subject = req.subject
        db.commit()

    tenants = TenantRepository().list_user_tenants(db, user.id)
    if not tenants:
        tenant_name = f"{user.display_name}'s Org"
        org = TenantRepository().create_tenant(db, name=tenant_name, owner_id=user.id)
        admin_role = MembershipRepository().get_role_by_name(db, "ADMIN")
        if admin_role:
            MembershipRepository().create_organization_membership(
                db, tenant_id=org.id, user_id=user.id, role_id=admin_role.id, is_owner=True
            )
        tenants = [org]

    active_tenant = tenants[0]
    mem_info = MembershipRepository().get_organization_membership(db, active_tenant.id, user.id)
    effective_role = "ADMIN"
    is_owner = True
    if mem_info:
        mem, role = mem_info
        effective_role = role.name
        is_owner = mem.is_owner

    roles_list = [effective_role]
    if is_owner:
        roles_list.append("OWNER")
    perms_list: list[str] = []
    for r in roles_list:
        perms_list.extend(list(ROLE_PERMISSIONS_MAP.get(r.upper(), [])))

    settings = get_settings()
    token = issue_user_token(
        subject=user.subject,
        email=user.email,
        display_name=user.display_name,
        tenant_id=active_tenant.id,
        roles=roles_list,
        permissions=perms_list,
        tenant_memberships=[{"tenant_id": active_tenant.id, "roles": roles_list}],
        is_owner=is_owner,
        read_only_demo=False,
    )

    return AuthResultResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_demo_token_minutes * 60,
        user=AuthUserResponse(
            id=user.id,
            subject=user.subject,
            email=user.email,
            display_name=user.display_name,
            has_organization=True,
            organizations_count=len(tenants),
            active_organization_id=active_tenant.id,
            effective_role=effective_role,
        ),
    )


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=1)


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest) -> dict[str, str]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset delivery is not configured. Use the identity provider's recovery flow or contact an administrator.",
    )


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest) -> dict[str, str]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset is not configured for this deployment. Use the identity provider's recovery flow or contact an administrator.",
    )


def _seed_demo_sample_data(tenant_id: str, project_id: str, environment_id: str, subject: str) -> None:
    from datetime import UTC, date, datetime
    from platform_api.changes.repository import change_repository
    from platform_api.changes.schemas import ChangeEventCreate, ChangeType
    from platform_api.finops.repository import finops_repository
    from platform_api.finops.schemas import CostRecordCreate, UtilizationCreate
    from platform_api.incidents.repository import IncidentSeverity
    from platform_api.incidents.schemas import IncidentCreate
    from platform_api.incidents.service import incident_repository
    from platform_api.inventory.schemas import InventoryResource, ResourceKind
    from platform_api.inventory.service import inventory_repository
    from platform_api.rag_service.schemas import DocumentCreate, DocumentType
    from platform_api.rag_service.service import ingest_document, repository as rag_repo

    now = datetime.now(UTC)

    # 1. Incidents
    if not incident_repository.list(tenant_id):
        incident_repository.create(
            tenant_id,
            IncidentCreate(
                title="checkout-api P1 latency degradation (504 Gateway Timeouts)",
                severity=IncidentSeverity.P1,
                service="checkout-api",
                environment="Production",
                started_at=now,
                summary="Elevated 504 gateway timeouts observed on checkout-api service.",
                description="Elevated 504 gateway timeouts observed on checkout-api service.",
                source="prometheus-alertmanager",
            ),
        )
        incident_repository.create(
            tenant_id,
            IncidentCreate(
                title="payment-gateway rate-limit saturation",
                severity=IncidentSeverity.P2,
                service="payment-gateway",
                environment="Production",
                started_at=now,
                summary="Payment gateway upstream connection rate limits reached 92% capacity.",
                description="Payment gateway upstream connection rate limits reached 92% capacity.",
                source="datadog",
            ),
        )
        incident_repository.create(
            tenant_id,
            IncidentCreate(
                title="redis-cluster high memory eviction alert",
                severity=IncidentSeverity.P3,
                service="redis-cache",
                environment="Staging",
                started_at=now,
                summary="Staging redis cache memory usage crossed 85% threshold with key eviction spikes.",
                description="Staging redis cache memory usage crossed 85% threshold with key eviction spikes.",
                source="aws-cloudwatch",
            ),
        )

    # 2. FinOps
    if not finops_repository.get_costs(tenant_id):
        finops_repository.add_cost(
            tenant_id,
            CostRecordCreate(
                period=date(2026, 10, 1),
                provider="AWS",
                account="123456789012",
                service="compute-engine",
                environment="Production",
                amount_usd=4250.00,
            ),
        )
        finops_repository.add_cost(
            tenant_id,
            CostRecordCreate(
                period=date(2026, 10, 1),
                provider="GCP",
                account="agentops-prod",
                service="kubernetes-engine",
                environment="Production",
                amount_usd=3120.00,
            ),
        )
        finops_repository.add_cost(
            tenant_id,
            CostRecordCreate(
                period=date(2026, 10, 1),
                provider="AWS",
                account="123456789012",
                service="rds-postgres",
                environment="Production",
                amount_usd=1850.00,
            ),
        )
        finops_repository.add_cost(
            tenant_id,
            CostRecordCreate(
                period=date(2026, 10, 1),
                provider="GCP",
                account="agentops-prod",
                service="cloud-storage",
                environment="Production",
                amount_usd=640.00,
            ),
        )
        finops_repository.add_utilization(
            tenant_id,
            UtilizationCreate(
                observed_on=date(2026, 10, 14),
                resource_id="k8s-worker-pool-01",
                service="kubernetes-engine",
                environment="Production",
                cpu_percent=14.2,
                memory_percent=38.5,
                monthly_cost_usd=1200.00,
            ),
        )
        finops_repository.add_utilization(
            tenant_id,
            UtilizationCreate(
                observed_on=date(2026, 10, 14),
                resource_id="db-replica-unused-02",
                service="rds-postgres",
                environment="Production",
                cpu_percent=2.1,
                memory_percent=3.4,
                monthly_cost_usd=450.00,
            ),
        )

    # 3. Inventory
    if not inventory_repository.list_for_tenant(tenant_id):
        inventory_repository.replace_for_tenant(
            tenant_id,
            [
                InventoryResource(
                    resource_id="k8s-cluster-prod",
                    provider="GCP",
                    kind=ResourceKind.KUBERNETES,
                    name="k8s-cluster-prod",
                    region="us-central1",
                    environment="Production",
                    service="kubernetes-engine",
                    status="healthy",
                ),
                InventoryResource(
                    resource_id="checkout-api-deploy",
                    provider="kubernetes",
                    kind=ResourceKind.COMPUTE,
                    name="checkout-api-deploy",
                    region="us-central1",
                    environment="Production",
                    service="checkout-api",
                    status="degraded",
                ),
                InventoryResource(
                    resource_id="postgres-primary-prod",
                    provider="AWS",
                    kind=ResourceKind.DATABASE,
                    name="postgres-primary-prod",
                    region="us-east-1",
                    environment="Production",
                    service="rds-postgres",
                    status="healthy",
                ),
                InventoryResource(
                    resource_id="payment-gateway-service",
                    provider="kubernetes",
                    kind=ResourceKind.NETWORK,
                    name="payment-gateway-service",
                    region="us-central1",
                    environment="Production",
                    service="payment-gateway",
                    status="healthy",
                ),
            ],
        )

    # 4. Changes
    if not change_repository.list_for_tenant(tenant_id):
        change_repository.create(
            tenant_id,
            ChangeEventCreate(
                service="checkout-api",
                environment="Production",
                change_type=ChangeType.DEPLOYMENT,
                title="Deployment of revision v2.18.4 (commit a1b2c3d)",
                source="argocd",
                actor="dev-deployer",
                occurred_at=now,
                details={"commit": "a1b2c3d", "image": "checkout-api:v2.18.4"},
            ),
        )
        change_repository.create(
            tenant_id,
            ChangeEventCreate(
                service="checkout-api",
                environment="Production",
                change_type=ChangeType.CONFIGURATION,
                title="ConfigMap update: DB connection pool size decreased from 50 to 20",
                source="kubernetes.configmap",
                actor="sre-operator",
                occurred_at=now,
                details={"key": "DB_POOL_SIZE", "old_val": "50", "new_val": "20"},
            ),
        )

    # 5. RAG Documents
    if not rag_repo.list_documents(tenant_id):
        ingest_document(
            tenant_id,
            DocumentCreate(
                source="docs/runbooks/checkout-api-504.md",
                title="SRE Incident Response Runbook: Checkout API Latency Degradation",
                content="Runbook for investigating checkout-api 504 gateway timeouts. Check upstream connection pool, database slow query log, and roll back deployment if v2.18.4 was recently deployed.",
                document_type=DocumentType.RUNBOOK,
                scope="project",
                service="checkout-api",
                environment="Production",
                tags=["runbook", "sre", "checkout-api"],
                allowed_roles=["READ", "WRITE", "ADMIN"],
            ),
            project_id=project_id,
            environment_id=environment_id,
        )
        ingest_document(
            tenant_id,
            DocumentCreate(
                source="docs/arch/prod-ha.md",
                title="Production Architecture & High Availability Invariants",
                content="Production architecture specifications. Cross-region failover, pgvector indexing, Keycloak OIDC authentication, and MCP isolation guidelines.",
                document_type=DocumentType.ARCHITECTURE,
                scope="project",
                service="platform",
                environment="Production",
                tags=["architecture", "security", "invariants"],
                allowed_roles=["READ", "WRITE", "ADMIN"],
            ),
            project_id=project_id,
            environment_id=environment_id,
        )


@router.post("/demo", response_model=AuthResultResponse)
@router.post("/demo-login", response_model=AuthResultResponse)
async def demo_login(
    db: Annotated[Session, Depends(get_db)],
) -> AuthResultResponse:
    settings = get_settings()
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo authentication is disabled",
        )

    demo_email = "alex.rivera@enterprise.com"
    user = MembershipRepository().get_user_by_email(db, demo_email)
    if not user:
        user = MembershipRepository().create_user_with_password(
            db,
            display_name="Alex Rivera",
            email=demo_email,
            password="DemoPassword123!",
        )

    tenants = TenantRepository().list_user_tenants(db, user.id)
    if not tenants:
        demo_tenant = TenantRepository().create_tenant(
            db,
            name="Enterprise Systems Corp (Demo)",
            slug=f"enterprise-systems-demo-{user.id[:8]}",
            description="Autonomous SRE, FinOps & LLMOps Platform Demo Workspace",
            created_by=user.id,
        )
        MembershipRepository().add_organization_member(
            db, tenant_id=demo_tenant.id, user_id=user.id, role_name="READ", is_owner=False
        )
        tenants = [demo_tenant]

    active_tenant = tenants[0]

    # Ensure demo project exists
    all_projects = ProjectRepository().list_projects(db, active_tenant.id)
    if not all_projects:
        demo_project = ProjectRepository().create_project(
            db,
            tenant_id=active_tenant.id,
            name="Cloud Operations",
            slug="cloud-operations",
            description="Autonomous SRE, FinOps & LLMOps Platform Demo Workspace",
            created_by=user.id,
        )
    else:
        demo_project = all_projects[0]

    # Ensure user has project membership
    pm = MembershipRepository().get_project_membership(db, demo_project.id, user.id)
    if not pm:
        MembershipRepository().add_project_member(
            db, project_id=demo_project.id, user_id=user.id, role_name="READ"
        )

    # Ensure environments exist (Production, Staging, Development)
    all_envs = EnvironmentRepository().list_environments(db, active_tenant.id, demo_project.id)
    existing_types = {e.type for e in all_envs}
    env_types = ["Production", "Staging", "Development"]
    for etype in env_types:
        if etype not in existing_types:
            env = EnvironmentRepository().create_environment(
                db,
                tenant_id=active_tenant.id,
                project_id=demo_project.id,
                name=etype,
                slug=etype.lower(),
                env_type=etype,
                description=f"Demo {etype} environment.",
                created_by=user.id,
            )
            all_envs.append(env)

    # Ensure user has membership in all environments
    for env in all_envs:
        em = MembershipRepository().get_environment_membership(db, env.id, user.id)
        if not em:
            MembershipRepository().add_environment_member(
                db, environment_id=env.id, user_id=user.id, role_name="READ"
            )

    prod_env = next((e for e in all_envs if e.type == "Production"), all_envs[0])
    db.commit()

    # Seed deterministic demo sample data if empty
    _seed_demo_sample_data(active_tenant.id, demo_project.id, prod_env.id, user.subject)

    roles_list = ["READ"]
    perms_list = list(ROLE_PERMISSIONS_MAP.get("READ", []))

    token = issue_user_token(
        subject=user.subject,
        email=user.email,
        display_name=user.display_name,
        tenant_id=active_tenant.id,
        roles=roles_list,
        permissions=perms_list,
        tenant_memberships=[{"tenant_id": active_tenant.id, "roles": roles_list}],
        project_id=demo_project.id,
        environment_id=prod_env.id,
        is_owner=False,
        read_only_demo=True,
    )

    return AuthResultResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_demo_token_minutes * 60,
        user=AuthUserResponse(
            id=user.id,
            subject=user.subject,
            email=user.email,
            display_name=user.display_name,
            has_organization=True,
            organizations_count=1,
            active_organization_id=active_tenant.id,
            active_project_id=demo_project.id,
            active_environment_id=prod_env.id,
            effective_role="READ",
            read_only_demo=True,
        ),
    )


@router.post("/demo-token", response_model=TokenResponse)
async def demo_token() -> TokenResponse:
    settings = get_settings()
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo authentication is disabled",
        )
    return TokenResponse(
        access_token=issue_demo_token(
            roles=("READ",),
            permissions=tuple(ROLE_PERMISSIONS_MAP["READ"]),
            read_only_demo=True,
        ),
        expires_in=settings.jwt_demo_token_minutes * 60,
        read_only_demo=True,
    )


@router.get("/me", response_model=PrincipalResponse)
async def current_user(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> PrincipalResponse:
    aud = (
        list(principal.audience)
        if isinstance(principal.audience, tuple | list | set)
        else principal.audience
    )
    return PrincipalResponse(
        subject=principal.subject,
        subject_id=principal.subject_id or principal.subject,
        tenant_id=principal.tenant_id,
        tenant_memberships=list(principal.tenant_memberships),
        roles=sorted(principal.roles),
        permissions=sorted(principal.permissions),
        issuer=principal.issuer,
        audience=aud,
        authentication_context=principal.authentication_context,
        session_id=principal.session_id,
        project_id=principal.project_id,
        environment_id=principal.environment_id,
        is_owner=principal.is_owner,
        read_only_demo=principal.read_only_demo,
    )
