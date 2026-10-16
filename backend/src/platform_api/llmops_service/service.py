import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from platform_api.identity_models import Group, UserGroup
from platform_api.identity_repository import AuditLogRepository
from platform_api.llmops_service.models import (
    LLMRequestModel,
    ModelAccessPolicy,
    ModelAdministrator,
    ModelScopeBinding,
    RegisteredModel,
)
from platform_api.llmops_service.providers import get_provider_adapter
from platform_api.llmops_service.repository import llmops_repository
from platform_api.llmops_service.schemas import (
    CredentialRotateRequest,
    EvaluationCreate,
    EvaluationResult,
    GatewayChatCompletionRequest,
    GatewayChatCompletionResponse,
    GroupCreate,
    GroupResponse,
    ModelAccessPolicyCreate,
    ModelAccessPolicyResponse,
    ModelAdminResponse,
    PromptVersion,
    PromptVersionCreate,
    RegisteredModelCreate,
    RegisteredModelResponse,
    RegisteredModelUpdate,
    TestConnectionResponse,
    TestCredentialRequest,
    new_id,
    now,
)
from platform_api.secrets.schemas import SecretCreate, SecretUpdate
from platform_api.secrets.service import SecretService
from platform_api.security import Principal

logger = logging.getLogger(__name__)


# --- Audit Helper ---
def _record_llm_audit(
    db: Session,
    principal: Principal,
    action: str,
    resource_id: str,
    details: dict[str, Any] | None = None,
):
    AuditLogRepository().record_event(
        session=db,
        actor=principal.subject,
        actor_email=principal.email,
        action=action,
        resource_type="llm_model",
        resource_id=resource_id,
        organization_id=principal.tenant_id,
        project_id=principal.project_id,
        environment_id=principal.environment_id,
        details=details or {},
    )


# --- Helper to Check Administrative Permissions ---
def _is_model_admin(db: Session, principal: Principal, model: RegisteredModel) -> bool:
    """Checks if principal is a model administrator or platform/tenant admin."""
    # Check platform/tenant admin roles or permissions
    if (
        "platform:admin" in principal.permissions
        or "platform.admin" in principal.permissions
        or "llm:admin" in principal.permissions
        or "ADMIN" in [r.upper() for r in principal.roles]
        or "OWNER" in [r.upper() for r in principal.roles]
    ):
        return True

    # Check explicit model administrator entry
    admin_record = db.scalar(
        select(ModelAdministrator).where(
            ModelAdministrator.model_id == model.id,
            ModelAdministrator.user_id.in_([principal.subject, principal.email]),
        )
    )
    if admin_record is not None:
        return True

    # Check model creator
    if model.created_by in (principal.subject, principal.email):
        return True

    return False


# --- Helper to Compute Effective Permissions ---
def _resolve_effective_permissions(
    db: Session, principal: Principal, model: RegisteredModel
) -> list[str]:
    if _is_model_admin(db, principal, model):
        return ["use", "view_metadata", "manage_access", "manage_model", "view_usage"]

    # Retrieve user's group IDs
    group_ids = db.scalars(
        select(UserGroup.group_id).where(UserGroup.user_id == principal.subject)
    ).all()

    policies = db.scalars(
        select(ModelAccessPolicy).where(ModelAccessPolicy.model_id == model.id)
    ).all()

    perms = set()
    for policy in policies:
        # Deny checks take absolute precedence
        if policy.effect == "deny":
            match_grantee = (
                (
                    policy.grantee_type == "user"
                    and policy.grantee_id in (principal.subject, principal.email)
                )
                or (policy.grantee_type == "group" and policy.grantee_id in group_ids)
                or (policy.grantee_type == "public_org")
            )
            if match_grantee:
                return []  # Explicit deny strips all permissions

    for policy in policies:
        if policy.effect == "allow":
            match_grantee = (
                (
                    policy.grantee_type == "user"
                    and policy.grantee_id in (principal.subject, principal.email)
                )
                or (policy.grantee_type == "group" and policy.grantee_id in group_ids)
                or (policy.grantee_type == "public_org")
            )
            if match_grantee:
                perms.add(policy.permission)

    if not perms and model.status == "active":
        # By default view_metadata is available if model is active and in tenant
        perms.add("view_metadata")

    return list(perms)


# --- Model Management Service ---

def test_provider_credentials(payload: TestCredentialRequest) -> TestConnectionResponse:
    adapter = get_provider_adapter(
        provider_name=payload.provider,
        model_name=payload.model_name,
        api_key=payload.api_key,
        base_url=payload.base_url,
        api_version=payload.api_version,
        provider_config=payload.provider_config,
    )
    return adapter.test_connection()


def register_model(
    db: Session, principal: Principal, payload: RegisteredModelCreate
) -> RegisteredModelResponse:
    # 1. Optionally test connection first
    if payload.test_connection_first:
        conn = test_provider_credentials(
            TestCredentialRequest(
                provider=payload.provider,
                model_name=payload.model_name,
                api_key=payload.api_key,
                base_url=payload.base_url,
                api_version=payload.api_version,
                provider_config=payload.provider_config,
            )
        )
        if not conn.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Credential validation failed: {conn.message}",
            )

    model_id = new_id()

    # 2. Store API Key in Secrets Service
    secret_svc = SecretService(db)
    default_prov = secret_svc.repo.get_default_provider(db, principal.tenant_id)
    secret_record = secret_svc.create_secret(
        principal=principal,
        req=SecretCreate(
            name=f"llm-key-{payload.provider}-{payload.model_name[:20]}-{model_id[:6]}",
            provider_id=default_prov.id,
            scope="organization",
            value=payload.api_key,
            description=f"Managed API Key for LLM Model {payload.display_name}",
        ),
    )

    # 3. Create Model Record
    model = RegisteredModel(
        id=model_id,
        tenant_id=principal.tenant_id,
        provider=payload.provider,
        model_name=payload.model_name,
        display_name=payload.display_name,
        description=payload.description,
        tags=payload.tags,
        capabilities=payload.capabilities,
        status="active",
        base_url=payload.base_url,
        api_version=payload.api_version,
        provider_config=payload.provider_config,
        secret_reference_id=secret_record.id,
        created_by=principal.subject,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(model)
    db.flush()

    # 4. Assign Creator as Initial Model Administrator
    admin_entry = ModelAdministrator(
        model_id=model_id,
        user_id=principal.subject,
        assigned_by=principal.subject,
        created_at=datetime.now(UTC),
    )
    db.add(admin_entry)

    # 5. Create Scope Bindings
    if payload.organization_wide:
        db.add(
            ModelScopeBinding(
                model_id=model_id,
                organization_id=principal.tenant_id,
                scope_type="organization",
            )
        )
    for p_id in payload.project_ids:
        db.add(
            ModelScopeBinding(
                model_id=model_id,
                organization_id=principal.tenant_id,
                project_id=p_id,
                scope_type="project",
            )
        )
    for e_id in payload.environment_ids:
        db.add(
            ModelScopeBinding(
                model_id=model_id,
                organization_id=principal.tenant_id,
                environment_id=e_id,
                scope_type="environment",
            )
        )

    # 6. Default Org Access Policy
    if payload.organization_wide:
        db.add(
            ModelAccessPolicy(
                model_id=model_id,
                organization_id=principal.tenant_id,
                grantee_type="public_org",
                permission="use",
                effect="allow",
                created_by=principal.subject,
            )
        )

    db.commit()
    db.refresh(model)

    _record_llm_audit(
        db,
        principal,
        "model.register",
        model.id,
        {
            "provider": payload.provider,
            "model_name": payload.model_name,
            "display_name": payload.display_name,
            "secret_reference_id": secret_record.id,
        },
    )

    return _to_model_response(db, principal, model)


def list_registered_models(db: Session, principal: Principal) -> list[RegisteredModelResponse]:
    models = db.scalars(
        select(RegisteredModel)
        .where(
            RegisteredModel.tenant_id == principal.tenant_id,
            RegisteredModel.status != "archived",
        )
        .order_by(RegisteredModel.created_at.desc())
    ).all()

    result = []
    for m in models:
        resp = _to_model_response(db, principal, m)
        if resp.effective_permissions or resp.is_administrator:
            result.append(resp)
    return result


def get_registered_model(
    db: Session, principal: Principal, model_id: str
) -> RegisteredModelResponse:
    model = db.scalar(
        select(RegisteredModel).where(
            RegisteredModel.id == model_id,
            RegisteredModel.tenant_id == principal.tenant_id,
        )
    )
    if not model or model.status == "archived":
        raise HTTPException(status_code=404, detail="Model not found.")
    return _to_model_response(db, principal, model)


def update_registered_model(
    db: Session, principal: Principal, model_id: str, payload: RegisteredModelUpdate
) -> RegisteredModelResponse:
    model = db.scalar(
        select(RegisteredModel).where(
            RegisteredModel.id == model_id,
            RegisteredModel.tenant_id == principal.tenant_id,
        )
    )
    if not model:
        raise HTTPException(status_code=404, detail="Model not found.")

    if not _is_model_admin(db, principal, model):
        raise HTTPException(
            status_code=403, detail="Only Model Administrators can modify model configuration."
        )

    if payload.display_name is not None:
        model.display_name = payload.display_name
    if payload.description is not None:
        model.description = payload.description
    if payload.status is not None:
        model.status = payload.status
    if payload.base_url is not None:
        model.base_url = payload.base_url
    if payload.api_version is not None:
        model.api_version = payload.api_version
    if payload.tags is not None:
        model.tags = payload.tags
    if payload.capabilities is not None:
        model.capabilities = payload.capabilities
    if payload.provider_config is not None:
        model.provider_config = payload.provider_config

    if payload.project_ids is not None or payload.environment_ids is not None:
        # Update scope bindings
        db.execute(delete(ModelScopeBinding).where(ModelScopeBinding.model_id == model_id))
        if payload.project_ids:
            for pid in payload.project_ids:
                db.add(
                    ModelScopeBinding(
                        model_id=model_id,
                        organization_id=principal.tenant_id,
                        project_id=pid,
                        scope_type="project",
                    )
                )
        if payload.environment_ids:
            for eid in payload.environment_ids:
                db.add(
                    ModelScopeBinding(
                        model_id=model_id,
                        organization_id=principal.tenant_id,
                        environment_id=eid,
                        scope_type="environment",
                    )
                )

    model.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(model)

    _record_llm_audit(
        db,
        principal,
        "model.update",
        model.id,
        {"updated_fields": payload.model_dump(exclude_unset=True)},
    )
    return _to_model_response(db, principal, model)


def rotate_model_credentials(
    db: Session, principal: Principal, model_id: str, payload: CredentialRotateRequest
) -> RegisteredModelResponse:
    model = db.scalar(
        select(RegisteredModel).where(
            RegisteredModel.id == model_id,
            RegisteredModel.tenant_id == principal.tenant_id,
        )
    )
    if not model:
        raise HTTPException(status_code=404, detail="Model not found.")

    if not _is_model_admin(db, principal, model):
        raise HTTPException(
            status_code=403, detail="Only Model Administrators can rotate API credentials."
        )

    if payload.test_connection:
        conn = test_provider_credentials(
            TestCredentialRequest(
                provider=model.provider,
                model_name=model.model_name,
                api_key=payload.api_key,
                base_url=model.base_url,
                api_version=model.api_version,
                provider_config=model.provider_config,
            )
        )
        if not conn.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Credential rotation failed: {conn.message}",
            )

    secret_svc = SecretService(db)
    if model.secret_reference_id:
        secret_svc.update_secret(
            principal=principal,
            secret_id=model.secret_reference_id,
            req=SecretUpdate(value=payload.api_key),
        )
    else:
        default_prov = secret_svc.repo.get_default_provider(db, principal.tenant_id)
        new_secret = secret_svc.create_secret(
            principal=principal,
            req=SecretCreate(
                name=f"llm-key-{model.provider}-{model.model_name[:20]}-{model_id[:6]}",
                provider_id=default_prov.id,
                scope="organization",
                value=payload.api_key,
                description=f"Managed API Key for LLM Model {model.display_name}",
            ),
        )
        model.secret_reference_id = new_secret.id

    model.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(model)

    _record_llm_audit(
        db,
        principal,
        "model.credential_rotate",
        model.id,
        {"secret_reference_id": model.secret_reference_id},
    )
    return _to_model_response(db, principal, model)


def delete_registered_model(db: Session, principal: Principal, model_id: str) -> dict[str, str]:
    model = db.scalar(
        select(RegisteredModel).where(
            RegisteredModel.id == model_id,
            RegisteredModel.tenant_id == principal.tenant_id,
        )
    )
    if not model:
        raise HTTPException(status_code=404, detail="Model not found.")

    if not _is_model_admin(db, principal, model):
        raise HTTPException(status_code=403, detail="Only Model Administrators can delete models.")

    model.status = "archived"
    model.updated_at = datetime.now(UTC)
    db.commit()

    _record_llm_audit(db, principal, "model.delete", model_id, {"status": "archived"})
    return {"message": f"Model '{model.display_name}' has been archived."}


# --- Model Administrator & Ownership Management ---

def assign_model_administrator(
    db: Session, principal: Principal, model_id: str, target_user_id: str
) -> ModelAdminResponse:
    model = db.scalar(
        select(RegisteredModel).where(
            RegisteredModel.id == model_id,
            RegisteredModel.tenant_id == principal.tenant_id,
        )
    )
    if not model:
        raise HTTPException(status_code=404, detail="Model not found.")

    if not _is_model_admin(db, principal, model):
        raise HTTPException(
            status_code=403, detail="Permission denied: Requires Model Administrator status."
        )

    existing = db.scalar(
        select(ModelAdministrator).where(
            ModelAdministrator.model_id == model_id,
            ModelAdministrator.user_id == target_user_id,
        )
    )
    if existing:
        return ModelAdminResponse(
            id=existing.id,
            model_id=existing.model_id,
            user_id=existing.user_id,
            assigned_by=existing.assigned_by,
            created_at=existing.created_at,
        )

    admin_entry = ModelAdministrator(
        model_id=model_id,
        user_id=target_user_id,
        assigned_by=principal.subject,
    )
    db.add(admin_entry)
    db.commit()
    db.refresh(admin_entry)

    _record_llm_audit(
        db, principal, "model.admin_assign", model_id, {"target_user_id": target_user_id}
    )
    return ModelAdminResponse(
        id=admin_entry.id,
        model_id=admin_entry.model_id,
        user_id=admin_entry.user_id,
        assigned_by=admin_entry.assigned_by,
        created_at=admin_entry.created_at,
    )


def remove_model_administrator(
    db: Session, principal: Principal, model_id: str, target_user_id: str
) -> dict[str, str]:
    model = db.scalar(
        select(RegisteredModel).where(
            RegisteredModel.id == model_id,
            RegisteredModel.tenant_id == principal.tenant_id,
        )
    )
    if not model:
        raise HTTPException(status_code=404, detail="Model not found.")

    if not _is_model_admin(db, principal, model):
        raise HTTPException(
            status_code=403, detail="Permission denied: Requires Model Administrator status."
        )

    admins = db.scalars(
        select(ModelAdministrator).where(ModelAdministrator.model_id == model_id)
    ).all()
    if len(admins) <= 1 and any(a.user_id == target_user_id for a in admins):
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot remove the last Model Administrator. Transfer ownership "
                "or assign another administrator first."
            ),
        )

    db.execute(
        delete(ModelAdministrator).where(
            ModelAdministrator.model_id == model_id,
            ModelAdministrator.user_id == target_user_id,
        )
    )
    db.commit()

    _record_llm_audit(
        db, principal, "model.admin_remove", model_id, {"target_user_id": target_user_id}
    )
    return {"message": f"User '{target_user_id}' removed as Model Administrator."}


def list_model_administrators(
    db: Session, principal: Principal, model_id: str
) -> list[ModelAdminResponse]:
    admins = db.scalars(
        select(ModelAdministrator).where(ModelAdministrator.model_id == model_id)
    ).all()
    return [
        ModelAdminResponse(
            id=a.id,
            model_id=a.model_id,
            user_id=a.user_id,
            assigned_by=a.assigned_by,
            created_at=a.created_at,
        )
        for a in admins
    ]


# --- Model Access Policy Management ---

def create_model_access_policy(
    db: Session, principal: Principal, model_id: str, payload: ModelAccessPolicyCreate
) -> ModelAccessPolicyResponse:
    model = db.scalar(
        select(RegisteredModel).where(
            RegisteredModel.id == model_id,
            RegisteredModel.tenant_id == principal.tenant_id,
        )
    )
    if not model:
        raise HTTPException(status_code=404, detail="Model not found.")

    if not _is_model_admin(db, principal, model):
        raise HTTPException(
            status_code=403,
            detail=(
                "Permission denied: Requires Model Administrator status to grant "
                "or revoke model access."
            ),
        )

    policy = ModelAccessPolicy(
        model_id=model_id,
        organization_id=principal.tenant_id,
        project_id=payload.project_id,
        environment_id=payload.environment_id,
        grantee_type=payload.grantee_type,
        grantee_id=payload.grantee_id,
        permission=payload.permission,
        effect=payload.effect,
        created_by=principal.subject,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)

    _record_llm_audit(
        db,
        principal,
        "model.policy_create",
        model_id,
        {"policy_id": policy.id, "grantee_type": payload.grantee_type, "effect": payload.effect},
    )
    return _to_policy_response(policy)


def list_model_access_policies(
    db: Session, principal: Principal, model_id: str
) -> list[ModelAccessPolicyResponse]:
    policies = db.scalars(
        select(ModelAccessPolicy).where(ModelAccessPolicy.model_id == model_id)
    ).all()
    return [_to_policy_response(p) for p in policies]


def delete_model_access_policy(db: Session, principal: Principal, policy_id: str) -> dict[str, str]:
    policy = db.scalar(select(ModelAccessPolicy).where(ModelAccessPolicy.id == policy_id))
    if not policy:
        raise HTTPException(status_code=404, detail="Access policy not found.")

    model = db.scalar(select(RegisteredModel).where(RegisteredModel.id == policy.model_id))
    if not model or not _is_model_admin(db, principal, model):
        raise HTTPException(status_code=403, detail="Requires Model Administrator status.")

    db.delete(policy)
    db.commit()

    _record_llm_audit(
        db, principal, "model.policy_delete", policy.model_id, {"policy_id": policy_id}
    )
    return {"message": "Access policy revoked."}


# --- User Group Service ---

def create_user_group(db: Session, principal: Principal, payload: GroupCreate) -> GroupResponse:
    slug = payload.slug or payload.name.lower().replace(" ", "-")
    group = Group(
        tenant_id=principal.tenant_id,
        name=payload.name,
        slug=slug,
        description=payload.description,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return GroupResponse(
        id=group.id,
        tenant_id=group.tenant_id,
        name=group.name,
        slug=group.slug,
        description=group.description,
        member_count=0,
        created_at=group.created_at,
    )


def list_user_groups(db: Session, principal: Principal) -> list[GroupResponse]:
    groups = db.scalars(select(Group).where(Group.tenant_id == principal.tenant_id)).all()
    res = []
    for g in groups:
        count = db.scalar(select(UserGroup).where(UserGroup.group_id == g.id))
        res.append(
            GroupResponse(
                id=g.id,
                tenant_id=g.tenant_id,
                name=g.name,
                slug=g.slug,
                description=g.description,
                member_count=1 if count else 0,
                created_at=g.created_at,
            )
        )
    return res


def add_user_to_group(
    db: Session, principal: Principal, group_id: str, user_id: str
) -> dict[str, str]:
    ug = UserGroup(group_id=group_id, user_id=user_id)
    db.add(ug)
    db.commit()
    return {"message": f"User '{user_id}' added to group '{group_id}'."}


# --- Mandatory Identity & Scope Authorization Engine ---

def invoke_chat_completion(
    db: Session, principal: Principal, request: GatewayChatCompletionRequest
) -> GatewayChatCompletionResponse:
    # 1. Identity & Tenant Check
    target_tenant = request.organization_id or principal.tenant_id
    if target_tenant != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-organization model invocation is strictly forbidden.",
        )

    # 2. Resolve Target Model
    model = db.scalar(
        select(RegisteredModel).where(
            (RegisteredModel.id == request.model) | (RegisteredModel.model_name == request.model),
            RegisteredModel.tenant_id == principal.tenant_id,
        )
    )
    if not model or model.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{request.model}' is not active or available in this organization.",
        )

    # 3. Scope Authorization Check (Project & Environment Scope)
    scope_bindings = db.scalars(
        select(ModelScopeBinding).where(ModelScopeBinding.model_id == model.id)
    ).all()

    bound_projects = [
        b.project_id for b in scope_bindings if b.scope_type == "project" and b.project_id
    ]
    if bound_projects and request.project_id and request.project_id not in bound_projects:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Model '{model.display_name}' is not enabled for requested "
                f"project '{request.project_id}'."
            ),
        )

    bound_envs = [
        b.environment_id
        for b in scope_bindings
        if b.scope_type == "environment" and b.environment_id
    ]
    if bound_envs and request.environment_id and request.environment_id not in bound_envs:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Model '{model.display_name}' is not enabled for requested "
                f"environment '{request.environment_id}'."
            ),
        )

    # 4. Mandatory Permission & Explicit Deny Check
    effective_perms = _resolve_effective_permissions(db, principal, model)
    if "use" not in effective_perms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Access Denied: Caller does not have 'use' permission "
                f"for model '{model.display_name}'."
            ),
        )

    # 5. Secure Credential Retrieval
    api_key = "mock-key-default"
    if model.secret_reference_id:
        try:
            secret_svc = SecretService(db)
            secret_val_resp = secret_svc.reveal_secret_value(principal, model.secret_reference_id)
            api_key = secret_val_resp.value
        except Exception as exc:
            logger.warning(
                "Could not resolve secret for model %s; falling back to adapter default: %s",
                model.id,
                exc,
            )

    # 6. Select Provider Adapter & Execute
    adapter = get_provider_adapter(
        provider_name=model.provider,
        model_name=model.model_name,
        api_key=api_key,
        base_url=model.base_url,
        api_version=model.api_version,
        provider_config=model.provider_config,
    )

    response = adapter.execute_chat_completion(request)

    # 7. Record Telemetry & Usage Record
    usage_entry = LLMRequestModel(
        tenant_id=principal.tenant_id,
        model_id=model.id,
        user_id=principal.subject,
        project_id=request.project_id or principal.project_id,
        environment_id=request.environment_id or principal.environment_id,
        provider=model.provider,
        model_name=model.model_name,
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        total_tokens=response.usage.total_tokens,
        latency_ms=response.latency_ms,
        estimated_cost_usd=response.estimated_cost_usd,
        status="success",
    )
    db.add(usage_entry)
    db.commit()

    # 8. Record Security Audit (Without Prompt Content or Key)
    _record_llm_audit(
        db,
        principal,
        "model.invoke",
        model.id,
        {
            "provider": model.provider,
            "model_name": model.model_name,
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "estimated_cost_usd": response.estimated_cost_usd,
            "latency_ms": response.latency_ms,
        },
    )

    return response


# --- Helper Serialization Functions ---

def _to_model_response(
    db: Session, principal: Principal, model: RegisteredModel
) -> RegisteredModelResponse:
    is_admin = _is_model_admin(db, principal, model)
    perms = _resolve_effective_permissions(db, principal, model)

    scope_bindings = db.scalars(
        select(ModelScopeBinding).where(ModelScopeBinding.model_id == model.id)
    ).all()
    p_ids = [b.project_id for b in scope_bindings if b.project_id]
    e_ids = [b.environment_id for b in scope_bindings if b.environment_id]

    return RegisteredModelResponse(
        id=model.id,
        tenant_id=model.tenant_id,
        provider=model.provider,
        model_name=model.model_name,
        display_name=model.display_name,
        description=model.description,
        tags=model.tags or [],
        capabilities=model.capabilities or [],
        status=model.status,
        base_url=model.base_url,
        api_version=model.api_version,
        provider_config=model.provider_config or {},
        credential_status="configured" if model.secret_reference_id else "missing",
        credential_masked="●●●●●●●●",
        created_by=model.created_by,
        is_administrator=is_admin,
        effective_permissions=perms,
        project_ids=p_ids,
        environment_ids=e_ids,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_policy_response(policy: ModelAccessPolicy) -> ModelAccessPolicyResponse:
    return ModelAccessPolicyResponse(
        id=policy.id,
        model_id=policy.model_id,
        organization_id=policy.organization_id,
        project_id=policy.project_id,
        environment_id=policy.environment_id,
        grantee_type=policy.grantee_type,
        grantee_id=policy.grantee_id,
        permission=policy.permission,
        effect=policy.effect,
        created_by=policy.created_by,
        created_at=policy.created_at,
    )


# --- Retained Legacy Functions for Compatibility ---

def create_prompt(tenant_id: str, payload: PromptVersionCreate) -> PromptVersion:
    prompt = PromptVersion(
        **payload.model_dump(),
        id=new_id(),
        tenant_id=tenant_id,
        created_at=now(),
    )
    return llmops_repository.add_prompt(prompt)


def evaluate(tenant_id: str, payload: EvaluationCreate) -> EvaluationResult:
    if payload.expected_text is None:
        correctness = 1.0 if payload.output_text.strip() else 0.0
    else:
        correctness = _token_overlap(payload.output_text, payload.expected_text)
    groundedness = 1.0 if payload.grounded else 0.0
    tool_call_correctness = 1.0 if payload.tool_call_correct else 0.0
    success = correctness >= 0.7 and groundedness >= 0.7 and tool_call_correctness >= 0.7
    result = EvaluationResult(
        id=new_id(),
        tenant_id=tenant_id,
        dataset=payload.dataset,
        model=payload.model,
        correctness=round(correctness, 4),
        groundedness=groundedness,
        retrieval_quality=payload.retrieval_quality,
        tool_call_correctness=tool_call_correctness,
        latency_ms=payload.latency_ms,
        estimated_cost_usd=payload.estimated_cost_usd,
        success=success,
        created_at=now(),
    )
    return llmops_repository.add_evaluation(result)


def _token_overlap(output: str, expected: str) -> float:
    output_tokens = set(output.lower().split())
    expected_tokens = set(expected.lower().split())
    if not expected_tokens:
        return 1.0
    return len(output_tokens.intersection(expected_tokens)) / len(expected_tokens)
