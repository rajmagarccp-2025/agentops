from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from platform_api.config import get_settings
from platform_api.identity_repository import AuditLogRepository
from platform_api.secrets.cache import get_secret_resolution_cache
from platform_api.secrets.models import Secret
from platform_api.secrets.providers.adapters import get_secret_provider_adapter
from platform_api.secrets.repository import SecretRepository
from platform_api.secrets.schemas import (
    SecretAssignmentCreate,
    SecretAssignmentResponse,
    SecretCreate,
    SecretMetadataResponse,
    SecretProviderCreate,
    SecretProviderResponse,
    SecretResolveRequest,
    SecretResolveResponse,
    SecretUpdate,
    SecretValueRevealResponse,
)
from platform_api.security import Principal


class SecretService:
    """Enforce scope rules, RBAC permissions, audit logging, and provider dispatch."""

    def __init__(self, db: Session, repo: SecretRepository | None = None):
        self.db = db
        self.repo = repo or SecretRepository()

    def _record_audit(
        self,
        principal: Principal,
        action: str,
        secret_id: str,
        organization_id: str | None = None,
        project_id: str | None = None,
        environment_id: str | None = None,
        target_entity: str | None = None,
        details: dict[str, Any] | None = None,
        outcome: str = "success",
    ) -> None:
        """Records security audit event for secret operations (NEVER logs raw values)."""
        det = details or {}
        det["outcome"] = outcome
        if target_entity:
            det["target_entity"] = target_entity

        AuditLogRepository().record_event(
            self.db,
            actor=principal.subject,
            actor_email=principal.email,
            action=action,
            resource_type="secret",
            resource_id=secret_id,
            organization_id=organization_id or principal.tenant_id,
            project_id=project_id or principal.project_id,
            environment_id=environment_id or principal.environment_id,
            details=det,
        )

    @staticmethod
    def _provider_secret_name(secret: Secret, provider: Any) -> str:
        if provider.provider_type != "gcp_secret_manager":
            return secret.name
        return (
            f"{secret.scope}|{secret.project_id or ''}|"
            f"{secret.environment_id or ''}|{secret.name}"
        )

    @staticmethod
    def _invalidate_runtime_secret_cache(secret: Secret) -> None:
        get_secret_resolution_cache().invalidate(secret.tenant_id, secret.id)

    # --- Scope and Permission Enforcement Helpers ---
    def _validate_scope_access(
        self, principal: Principal, secret: Secret, action_perm: str
    ) -> None:
        """Validate tenant, project, environment scope, and granular permissions."""
        # 1. Check Tenant Isolation
        if secret.tenant_id != principal.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-tenant access to secret is strictly forbidden.",
            )

        # 2. Check Granular Permission
        alt_perm = (
            action_perm.replace(".", ":") if "." in action_perm else action_perm.replace(":", ".")
        )
        has_perm = (
            action_perm in principal.permissions
            or alt_perm in principal.permissions
            or "platform:admin" in principal.permissions
            or "platform.admin" in principal.permissions
            or "platform-admin" in principal.roles
            or "ADMIN" in [r.upper() for r in principal.roles]
            or "OWNER" in [r.upper() for r in principal.roles]
        )
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{action_perm}' required for this secret operation.",
            )

        # 3. Hierarchical Scope Rules
        if secret.scope == "project":
            if (
                principal.project_id
                and secret.project_id
                and principal.project_id != secret.project_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Project-scoped secret is restricted to its owning project.",
                )
        elif secret.scope == "environment":
            if (
                principal.environment_id
                and secret.environment_id
                and principal.environment_id != secret.environment_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Environment-scoped secret is restricted to its assigned environment.",
                )

        # Prevent development/test resources from accessing Production secrets automatically
        if secret.environment_id:
            if principal.environment_id and principal.environment_id != secret.environment_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Production secrets cannot be accessed by non-production resources.",
                )

    def _build_metadata_response(self, secret: Secret) -> SecretMetadataResponse:
        provider = self.repo.get_provider_by_id(self.db, secret.provider_id)
        p_type = provider.provider_type if provider else "internal_encrypted"
        p_name = provider.name if provider else "Internal Encrypted"

        ver = self.repo.get_current_version(self.db, secret.id)
        vnum = ver.version_num if ver else 1

        assignments = self.repo.list_assignments(self.db, secret.id)
        asgn_responses = [
            SecretAssignmentResponse(
                id=a.id,
                secret_id=a.secret_id,
                entity_type=a.entity_type,
                entity_id=a.entity_id,
                entity_name=a.entity_name,
                assigned_by=a.assigned_by,
                assigned_at=a.assigned_at,
            )
            for a in assignments
        ]

        return SecretMetadataResponse(
            id=secret.id,
            name=secret.name,
            description=secret.description,
            secret_type=secret.secret_type,
            provider_id=secret.provider_id,
            provider_type=p_type,
            provider_name=p_name,
            scope=secret.scope,
            tenant_id=secret.tenant_id,
            project_id=secret.project_id,
            environment_id=secret.environment_id,
            current_version_num=vnum,
            created_by=secret.created_by,
            modified_by=secret.modified_by,
            created_at=secret.created_at,
            updated_at=secret.updated_at,
            status=secret.status,
            expiration_date=secret.expiration_date,
            rotation_interval_days=secret.rotation_interval_days,
            last_rotated_at=secret.last_rotated_at,
            metadata=secret.metadata_json or {},
            assigned_entities=asgn_responses,
        )

    # --- Provider Operations ---
    def configure_provider(
        self, principal: Principal, req: SecretProviderCreate
    ) -> SecretProviderResponse:
        if req.provider_type == "gcp_secret_manager":
            configured_project = get_settings().gcp_secret_manager_project_id
            if (
                not configured_project
                or req.vault_identifier != configured_project
                or req.endpoint_url
                or req.auth_method != "workload_identity"
                or req.credentials_config
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "GCP Secret Manager must use the configured project and "
                        "Workload Identity without custom endpoints or credentials."
                    ),
                )
        provider = self.repo.create_provider(
            session=self.db,
            tenant_id=principal.tenant_id,
            name=req.name,
            provider_type=req.provider_type,
            endpoint_url=req.endpoint_url,
            vault_identifier=req.vault_identifier,
            region=req.region,
            auth_method=req.auth_method,
            required_roles=req.required_roles,
            created_by=principal.subject,
        )

        # Execute connection validation
        adapter = get_secret_provider_adapter(provider)
        res = adapter.test_connection()
        status_str = "connected" if res.success else "error"
        self.repo.update_provider_status(self.db, provider.id, status_str, datetime.now(UTC))

        self._record_audit(
            principal,
            "secret_provider.configured",
            provider.id,
            details={"provider_type": req.provider_type, "status": status_str},
        )
        self.db.commit()

        return SecretProviderResponse(
            id=provider.id,
            tenant_id=provider.tenant_id,
            name=provider.name,
            provider_type=provider.provider_type,
            endpoint_url=provider.endpoint_url,
            vault_identifier=provider.vault_identifier,
            region=provider.region,
            auth_method=provider.auth_method,
            required_roles=provider.required_roles or [],
            status=provider.status,
            last_validated_at=provider.last_validated_at,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )

    def test_provider_connection(self, principal: Principal, provider_id: str) -> dict[str, Any]:
        provider = self.repo.get_provider_by_id(self.db, provider_id)
        if not provider or provider.tenant_id != principal.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Secret Provider not found."
            )

        adapter = get_secret_provider_adapter(provider)
        test_res = adapter.test_connection()
        status_str = "connected" if test_res.success else "error"
        self.repo.update_provider_status(self.db, provider.id, status_str, datetime.now(UTC))

        self._record_audit(
            principal,
            "secret_provider.tested",
            provider.id,
            details={"success": test_res.success, "message": test_res.message},
        )
        self.db.commit()

        return {
            "provider_id": provider.id,
            "success": test_res.success,
            "message": test_res.message,
            "status": status_str,
            "last_validated_at": provider.last_validated_at.isoformat()
            if provider.last_validated_at
            else None,
            "capabilities": test_res.capabilities.__dict__ if test_res.capabilities else {},
        }

    def list_providers(self, principal: Principal) -> list[SecretProviderResponse]:
        # Ensure default internal provider exists
        self.repo.get_default_provider(self.db, principal.tenant_id)
        providers = self.repo.list_providers(self.db, principal.tenant_id)

        return [
            SecretProviderResponse(
                id=p.id,
                tenant_id=p.tenant_id,
                name=p.name,
                provider_type=p.provider_type,
                endpoint_url=p.endpoint_url,
                vault_identifier=p.vault_identifier,
                region=p.region,
                auth_method=p.auth_method,
                required_roles=p.required_roles or [],
                status=p.status,
                last_validated_at=p.last_validated_at,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in providers
        ]

    # --- Secret CRUD Operations ---
    def create_secret(self, principal: Principal, req: SecretCreate) -> SecretMetadataResponse:
        if req.expiration_date is not None:
            expiration = (
                req.expiration_date.replace(tzinfo=UTC)
                if req.expiration_date.tzinfo is None
                else req.expiration_date.astimezone(UTC)
            )
            if expiration <= datetime.now(UTC):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Secret expiration_date must be in the future.",
                )

        # Validate provider exists
        provider = self.repo.get_provider_by_id(self.db, req.provider_id)
        if not provider or provider.tenant_id != principal.tenant_id:
            # Fallback to default internal provider if requested provider not found
            provider = self.repo.get_default_provider(self.db, principal.tenant_id)

        # Scope-aware ID resolution
        proj_id = req.project_id if req.scope != "organization" else None
        env_id = req.environment_id if req.scope not in ("organization", "project") else None
        if req.scope == "project" and not proj_id:
            proj_id = principal.project_id
        elif req.scope == "environment":
            proj_id = proj_id or principal.project_id
            env_id = env_id or principal.environment_id

        # Create Secret record
        secret = self.repo.create_secret(
            session=self.db,
            tenant_id=principal.tenant_id,
            name=req.name,
            provider_id=provider.id,
            created_by=principal.subject,
            description=req.description,
            secret_type=req.secret_type,
            scope=req.scope,
            project_id=proj_id,
            environment_id=env_id,
            expiration_date=req.expiration_date,
            rotation_interval_days=req.rotation_interval_days,
            metadata_json=req.metadata,
        )

        # Store secret value via provider adapter
        adapter = get_secret_provider_adapter(provider)
        provider_secret_name = self._provider_secret_name(secret, provider)
        v_ref, enc_val, enc_meta = adapter.create_secret(
            provider_secret_name, req.value, req.metadata
        )

        # Create initial Version (version 1)
        self.repo.create_version(
            session=self.db,
            secret_id=secret.id,
            version_num=1,
            created_by=principal.subject,
            provider_version_ref=v_ref,
            encrypted_value=enc_val,
            encryption_metadata=enc_meta,
            comment="Initial secret version created",
        )

        # Add entity assignments if provided
        for asgn in req.assignments:
            self.repo.assign_entity(
                self.db,
                secret.id,
                asgn.entity_type,
                asgn.entity_id,
                asgn.entity_name,
                principal.subject,
            )

        self._record_audit(
            principal,
            "secret.created",
            secret.id,
            organization_id=secret.tenant_id,
            project_id=secret.project_id,
            environment_id=secret.environment_id,
            details={
                "secret_name": secret.name,
                "secret_type": secret.secret_type,
                "scope": secret.scope,
                "provider_type": provider.provider_type,
            },
        )
        self.db.commit()

        return self._build_metadata_response(secret)

    def list_secrets(
        self,
        principal: Principal,
        project_id: str | None = None,
        environment_id: str | None = None,
        scope: str | None = None,
        secret_type: str | None = None,
        search: str | None = None,
    ) -> list[SecretMetadataResponse]:
        secrets = self.repo.list_secrets(
            self.db,
            tenant_id=principal.tenant_id,
            project_id=project_id or principal.project_id,
            environment_id=environment_id or principal.environment_id,
            scope=scope,
            secret_type=secret_type,
            search=search,
        )
        return [self._build_metadata_response(s) for s in secrets]

    def get_secret_metadata(self, principal: Principal, secret_id: str) -> SecretMetadataResponse:
        secret = self.repo.get_secret_by_id(self.db, secret_id)
        if not secret:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found.")

        self._validate_scope_access(principal, secret, "secrets.metadata.read")
        return self._build_metadata_response(secret)

    def reveal_secret_value(
        self, principal: Principal, secret_id: str
    ) -> SecretValueRevealResponse:
        """Tightly authorized, separate operation to reveal secret value with mandatory auditing."""
        secret = self.repo.get_secret_by_id(self.db, secret_id)
        if not secret:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found.")

        # Require explicit value read permission
        self._validate_scope_access(principal, secret, "secrets.value.read")

        version = self.repo.get_current_version(self.db, secret.id)
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Secret version not found."
            )

        provider = self.repo.get_provider_by_id(self.db, secret.provider_id)
        if not provider:
            provider = self.repo.get_default_provider(self.db, principal.tenant_id)

        adapter = get_secret_provider_adapter(provider)
        raw_value = adapter.read_secret_value(
            self._provider_secret_name(secret, provider),
            version_ref=version.provider_version_ref,
            encrypted_value=version.encrypted_value,
            encryption_metadata=version.encryption_metadata,
        )

        self._record_audit(
            principal,
            "secret.value_revealed",
            secret.id,
            organization_id=secret.tenant_id,
            project_id=secret.project_id,
            environment_id=secret.environment_id,
            details={"version_num": version.version_num},
        )
        self.db.commit()

        return SecretValueRevealResponse(
            secret_id=secret.id,
            secret_name=secret.name,
            version_num=version.version_num,
            value=raw_value,
            revealed_at=datetime.now(UTC),
            revealed_by=principal.subject,
        )

    def update_secret(
        self, principal: Principal, secret_id: str, req: SecretUpdate
    ) -> SecretMetadataResponse:
        secret = self.repo.get_secret_by_id(self.db, secret_id)
        if not secret:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found.")

        self._validate_scope_access(principal, secret, "secrets.update")
        if secret.status == "revoked":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A revoked secret cannot be reactivated or modified.",
            )
        if req.expiration_date is not None:
            expiration = (
                req.expiration_date.replace(tzinfo=UTC)
                if req.expiration_date.tzinfo is None
                else req.expiration_date.astimezone(UTC)
            )
            if expiration <= datetime.now(UTC):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Secret expiration_date must be in the future.",
                )

        if req.value:
            # Create a new version if secret value updated
            provider = self.repo.get_provider_by_id(self.db, secret.provider_id)
            if not provider:
                provider = self.repo.get_default_provider(self.db, principal.tenant_id)

            adapter = get_secret_provider_adapter(provider)
            provider_secret_name = self._provider_secret_name(secret, provider)
            v_ref, enc_val, enc_meta = adapter.update_secret_value(
                provider_secret_name, req.value
            )

            current_ver = self.repo.get_current_version(self.db, secret.id)
            next_num = (current_ver.version_num + 1) if current_ver else 1

            self.repo.create_version(
                session=self.db,
                secret_id=secret.id,
                version_num=next_num,
                created_by=principal.subject,
                provider_version_ref=v_ref,
                encrypted_value=enc_val,
                encryption_metadata=enc_meta,
                comment="Secret value updated",
            )
            # Invalidate runtime resolution cache
            self._invalidate_runtime_secret_cache(secret)

        if req.status is not None and req.status != secret.status:
            provider = self.repo.get_provider_by_id(self.db, secret.provider_id)
            if provider and provider.provider_type == "gcp_secret_manager":
                adapter = get_secret_provider_adapter(provider)
                if req.status in {"disabled", "pending_deletion"}:
                    adapter.delete_secret(self._provider_secret_name(secret, provider))
                else:
                    current_version = self.repo.get_current_version(self.db, secret.id)
                    if current_version and current_version.provider_version_ref:
                        adapter.set_secret_version_enabled(
                            self._provider_secret_name(secret, provider),
                            current_version.provider_version_ref,
                            enabled=True,
                        )
            if req.status in {"disabled", "pending_deletion"}:
                self._invalidate_runtime_secret_cache(secret)

        self.repo.update_secret_metadata(
            session=self.db,
            secret_id=secret.id,
            modified_by=principal.subject,
            description=req.description,
            expiration_date=req.expiration_date,
            rotation_interval_days=req.rotation_interval_days,
            status=req.status,
            metadata_json=req.metadata,
        )

        self._record_audit(
            principal,
            "secret.updated",
            secret.id,
            organization_id=secret.tenant_id,
            project_id=secret.project_id,
            environment_id=secret.environment_id,
            details={"value_updated": req.value is not None, "status": req.status},
        )
        self.db.commit()

        return self._build_metadata_response(secret)

    def rotate_secret(self, principal: Principal, secret_id: str) -> SecretMetadataResponse:
        secret = self.repo.get_secret_by_id(self.db, secret_id)
        if not secret:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found.")

        self._validate_scope_access(principal, secret, "secrets.rotate")
        if secret.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot rotate a secret with status '{secret.status}'.",
            )

        provider = self.repo.get_provider_by_id(self.db, secret.provider_id)
        if not provider:
            provider = self.repo.get_default_provider(self.db, principal.tenant_id)

        adapter = get_secret_provider_adapter(provider)
        current_ver = self.repo.get_current_version(self.db, secret.id)
        ref = current_ver.provider_version_ref if current_ver else None

        provider_secret_name = self._provider_secret_name(secret, provider)
        v_ref, enc_val, enc_meta = adapter.rotate_secret(provider_secret_name, ref)
        next_num = (current_ver.version_num + 1) if current_ver else 1

        self.repo.create_version(
            session=self.db,
            secret_id=secret.id,
            version_num=next_num,
            created_by=principal.subject,
            provider_version_ref=v_ref,
            encrypted_value=enc_val,
            encryption_metadata=enc_meta,
            comment=f"Rotated secret version {next_num}",
        )
        secret.last_rotated_at = datetime.now(UTC)
        secret.modified_by = principal.subject
        secret.updated_at = datetime.now(UTC)

        # Invalidate runtime cache
        self._invalidate_runtime_secret_cache(secret)

        self._record_audit(
            principal,
            "secret.rotated",
            secret.id,
            organization_id=secret.tenant_id,
            project_id=secret.project_id,
            environment_id=secret.environment_id,
            details={"new_version": next_num},
        )
        self.db.commit()

        return self._build_metadata_response(secret)

    def rollback_secret(
        self, principal: Principal, secret_id: str, target_version_num: int
    ) -> SecretMetadataResponse:
        secret = self.repo.get_secret_by_id(self.db, secret_id)
        if not secret:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found.")
        self._validate_scope_access(principal, secret, "secrets.rotate")
        if secret.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only active secrets can be rolled back.",
            )

        target_version = self.repo.get_version_by_num(self.db, secret.id, target_version_num)
        if not target_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Secret version not found."
            )
        provider = self.repo.get_provider_by_id(self.db, secret.provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Secret provider is unavailable.",
            )

        adapter = get_secret_provider_adapter(provider)
        restored_value = adapter.read_secret_value(
            self._provider_secret_name(secret, provider),
            version_ref=target_version.provider_version_ref,
            encrypted_value=target_version.encrypted_value,
            encryption_metadata=target_version.encryption_metadata,
        )
        current_version = self.repo.get_current_version(self.db, secret.id)
        next_version_num = current_version.version_num + 1 if current_version else 1
        version_ref, encrypted_value, encryption_metadata = adapter.update_secret_value(
            self._provider_secret_name(secret, provider), restored_value
        )
        self.repo.create_version(
            session=self.db,
            secret_id=secret.id,
            version_num=next_version_num,
            created_by=principal.subject,
            provider_version_ref=version_ref,
            encrypted_value=encrypted_value,
            encryption_metadata=encryption_metadata,
            comment=f"Restored from version {target_version_num}",
        )
        self._invalidate_runtime_secret_cache(secret)
        self._record_audit(
            principal,
            "secret.version_restored",
            secret.id,
            organization_id=secret.tenant_id,
            project_id=secret.project_id,
            environment_id=secret.environment_id,
            details={"restored_from_version": target_version_num, "new_version": next_version_num},
        )
        self.db.commit()
        return self._build_metadata_response(secret)

    def revoke_secret(self, principal: Principal, secret_id: str) -> dict[str, Any]:
        secret = self.repo.get_secret_by_id(self.db, secret_id)
        if not secret:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found.")
        self._validate_scope_access(principal, secret, "secrets.revoke")
        if secret.status == "revoked":
            return {"success": True, "status": "revoked"}
        provider = self.repo.get_provider_by_id(self.db, secret.provider_id)
        version = self.repo.get_current_version(self.db, secret.id)
        if (
            provider
            and provider.provider_type == "gcp_secret_manager"
            and version
            and version.provider_version_ref
        ):
            adapter = get_secret_provider_adapter(provider)
            adapter.delete_secret(self._provider_secret_name(secret, provider))
        secret.status = "revoked"
        secret.revoked_at = datetime.now(UTC)
        secret.revoked_by = principal.subject
        secret.modified_by = principal.subject
        secret.updated_at = datetime.now(UTC)
        self._invalidate_runtime_secret_cache(secret)
        self._record_audit(
            principal,
            "secret.revoked",
            secret.id,
            organization_id=secret.tenant_id,
            project_id=secret.project_id,
            environment_id=secret.environment_id,
        )
        self.db.commit()
        return {"success": True, "status": "revoked"}

    def delete_secret(self, principal: Principal, secret_id: str) -> dict[str, Any]:
        secret = self.repo.get_secret_by_id(self.db, secret_id)
        if not secret:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found.")

        self._validate_scope_access(principal, secret, "secrets.delete")

        provider = self.repo.get_provider_by_id(self.db, secret.provider_id)
        if provider:
            adapter = get_secret_provider_adapter(provider)
            adapter.delete_secret(self._provider_secret_name(secret, provider))

        self._record_audit(
            principal,
            "secret.deleted",
            secret.id,
            organization_id=secret.tenant_id,
            project_id=secret.project_id,
            environment_id=secret.environment_id,
            details={"secret_name": secret.name},
        )
        self.repo.delete_secret(self.db, secret.id)
        self.db.commit()

        if provider and provider.provider_type == "gcp_secret_manager":
            message = (
                f"Secret '{secret.name}' metadata was deleted and enabled GCP versions were "
                "disabled; the cloud resource remains retained."
            )
        else:
            message = f"Secret '{secret.name}' securely deleted."
        self._invalidate_runtime_secret_cache(secret)
        return {"success": True, "message": message}

    def assign_entity(
        self, principal: Principal, secret_id: str, req: SecretAssignmentCreate
    ) -> SecretAssignmentResponse:
        secret = self.repo.get_secret_by_id(self.db, secret_id)
        if not secret:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found.")

        self._validate_scope_access(principal, secret, "secrets.assign")

        assignment = self.repo.assign_entity(
            self.db, secret.id, req.entity_type, req.entity_id, req.entity_name, principal.subject
        )

        self._record_audit(
            principal,
            "secret.entity_assigned",
            secret.id,
            organization_id=secret.tenant_id,
            project_id=secret.project_id,
            environment_id=secret.environment_id,
            target_entity=f"{req.entity_type}:{req.entity_id}",
            details={"entity_name": req.entity_name},
        )
        self.db.commit()

        return SecretAssignmentResponse(
            id=assignment.id,
            secret_id=assignment.secret_id,
            entity_type=assignment.entity_type,
            entity_id=assignment.entity_id,
            entity_name=assignment.entity_name,
            assigned_by=assignment.assigned_by,
            assigned_at=assignment.assigned_at,
        )

    def revoke_assignment(
        self, principal: Principal, secret_id: str, assignment_id: str
    ) -> dict[str, Any]:
        secret = self.repo.get_secret_by_id(self.db, secret_id)
        if not secret:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found.")

        self._validate_scope_access(principal, secret, "secrets.unassign")

        res = self.repo.revoke_assignment(self.db, assignment_id)
        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found."
            )

        self._record_audit(
            principal,
            "secret.entity_unassigned",
            secret.id,
            organization_id=secret.tenant_id,
            project_id=secret.project_id,
            environment_id=secret.environment_id,
            details={"assignment_id": assignment_id},
        )
        self.db.commit()

        return {"success": True, "message": "Secret entity assignment revoked."}

    # --- Runtime Resolution Interface ---
    def resolve_runtime_secret(
        self, principal: Principal, req: SecretResolveRequest
    ) -> SecretResolveResponse:
        """Runtime API for workloads/agents to securely resolve secrets by name or ID."""
        # Find secret by UUID or Name
        secret = self.repo.get_secret_by_id(self.db, req.secret_identifier)
        if not secret:
            secret = self.repo.get_secret_by_name(
                self.db,
                tenant_id=principal.tenant_id,
                name=req.secret_identifier,
                project_id=req.project_id or principal.project_id,
                environment_id=req.environment_id or principal.environment_id,
            )

        if not secret or secret.tenant_id != principal.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Secret resolution failed: secret not found.",
            )

        if req.project_id and req.project_id != principal.project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Secret resolution cannot override the authenticated project context.",
            )
        if req.environment_id and req.environment_id != principal.environment_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Secret resolution cannot override the authenticated environment context.",
            )
        if secret.scope == "project" and (
            principal.project_id is None or secret.project_id != principal.project_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Secret resolution failed: secret not found.",
            )
        if secret.scope == "environment" and (
            principal.project_id is None
            or principal.environment_id is None
            or secret.project_id != principal.project_id
            or secret.environment_id != principal.environment_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Secret resolution failed: secret not found.",
            )

        if secret.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Secret is currently '{secret.status}'.",
            )
        if secret.expiration_date is not None:
            expires_at = (
                secret.expiration_date.replace(tzinfo=UTC)
                if secret.expiration_date.tzinfo is None
                else secret.expiration_date.astimezone(UTC)
            )
            if expires_at <= datetime.now(UTC):
                secret.status = "expired"
                secret.updated_at = datetime.now(UTC)
                self._record_audit(
                    principal,
                    "secret.expired",
                    secret.id,
                    organization_id=secret.tenant_id,
                    project_id=secret.project_id,
                    environment_id=secret.environment_id,
                    details={"expiration_date": expires_at.isoformat()},
                )
                self.db.commit()
                self._invalidate_runtime_secret_cache(secret)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Secret has expired.",
                )

        # Check entity assignment if specific workload entity requested
        if req.requesting_entity_id != "runtime":
            assigned = self.repo.is_entity_assigned(
                self.db, secret.id, req.requesting_entity_type, req.requesting_entity_id
            )
            if not assigned and secret.scope == "environment":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Entity '{req.requesting_entity_type}:{req.requesting_entity_id}' "
                        "is not authorized to access this secret."
                    ),
                )

        version = self.repo.get_current_version(self.db, secret.id)
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Secret has no active versions."
            )

        provider = self.repo.get_provider_by_id(self.db, secret.provider_id)
        if not provider:
            provider = self.repo.get_default_provider(self.db, principal.tenant_id)

        adapter = get_secret_provider_adapter(provider)
        secret_cache = get_secret_resolution_cache()
        raw_val = secret_cache.get(secret.tenant_id, secret.id, version.id)
        if raw_val is None:
            raw_val = adapter.read_secret_value(
                self._provider_secret_name(secret, provider),
                version_ref=version.provider_version_ref,
                encrypted_value=version.encrypted_value,
                encryption_metadata=version.encryption_metadata,
            )
            secret_cache.set(secret.tenant_id, secret.id, version.id, raw_val)

        self._record_audit(
            principal,
            "secret.runtime_resolved",
            secret.id,
            organization_id=secret.tenant_id,
            project_id=secret.project_id,
            environment_id=secret.environment_id,
            target_entity=f"{req.requesting_entity_type}:{req.requesting_entity_id}",
            details={"version_num": version.version_num},
        )
        self.db.commit()

        return SecretResolveResponse(
            secret_id=secret.id,
            secret_name=secret.name,
            version_num=version.version_num,
            value=raw_val,
            environment_id=secret.environment_id,
            provider_type=provider.provider_type,
        )
