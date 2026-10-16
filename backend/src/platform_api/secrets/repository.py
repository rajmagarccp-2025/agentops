from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from platform_api.secrets.models import (
    Secret,
    SecretAssignment,
    SecretProvider,
    SecretVersion,
)


class SecretRepository:
    """Data repository for Secret Management entities."""

    # --- Provider CRUD ---
    def create_provider(
        self,
        session: Session,
        tenant_id: str,
        name: str,
        provider_type: str,
        endpoint_url: str | None = None,
        vault_identifier: str | None = None,
        region: str | None = None,
        auth_method: str = "workload_identity",
        credentials_config_encrypted: str | None = None,
        required_roles: list[str] | None = None,
        created_by: str | None = None,
    ) -> SecretProvider:
        provider = SecretProvider(
            tenant_id=tenant_id,
            name=name,
            provider_type=provider_type,
            endpoint_url=endpoint_url,
            vault_identifier=vault_identifier,
            region=region,
            auth_method=auth_method,
            credentials_config_encrypted=credentials_config_encrypted,
            required_roles=required_roles or [],
            created_by=created_by,
            status="untested",
        )
        session.add(provider)
        session.flush()
        return provider

    def get_provider_by_id(self, session: Session, provider_id: str) -> SecretProvider | None:
        return session.scalar(select(SecretProvider).where(SecretProvider.id == provider_id))

    def list_providers(self, session: Session, tenant_id: str) -> list[SecretProvider]:
        return list(
            session.scalars(
                select(SecretProvider)
                .where(SecretProvider.tenant_id == tenant_id)
                .order_by(SecretProvider.name)
            ).all()
        )

    def get_default_provider(self, session: Session, tenant_id: str) -> SecretProvider:
        """Returns existing provider or auto-provisions internal AES-256-GCM encrypted provider."""
        provider = session.scalar(
            select(SecretProvider).where(
                SecretProvider.tenant_id == tenant_id,
                SecretProvider.provider_type == "internal_encrypted",
            )
        )
        if not provider:
            provider = self.create_provider(
                session=session,
                tenant_id=tenant_id,
                name="Internal Encrypted Vault",
                provider_type="internal_encrypted",
                auth_method="master_key",
            )
            provider.status = "connected"
            provider.last_validated_at = datetime.now(UTC)
            session.flush()
        return provider

    def update_provider_status(
        self,
        session: Session,
        provider_id: str,
        status: str,
        last_validated_at: datetime | None = None,
    ) -> SecretProvider | None:
        provider = self.get_provider_by_id(session, provider_id)
        if provider:
            provider.status = status
            provider.last_validated_at = last_validated_at or datetime.now(UTC)
            session.flush()
        return provider

    # --- Secret CRUD ---
    def create_secret(
        self,
        session: Session,
        tenant_id: str,
        name: str,
        provider_id: str,
        created_by: str,
        description: str = "",
        secret_type: str = "api_key",
        scope: str = "environment",
        project_id: str | None = None,
        environment_id: str | None = None,
        expiration_date: datetime | None = None,
        rotation_interval_days: int | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> Secret:
        secret = Secret(
            tenant_id=tenant_id,
            name=name,
            description=description,
            secret_type=secret_type,
            provider_id=provider_id,
            scope=scope,
            project_id=project_id,
            environment_id=environment_id,
            created_by=created_by,
            modified_by=created_by,
            expiration_date=expiration_date,
            rotation_interval_days=rotation_interval_days,
            metadata_json=metadata_json or {},
            status="active",
        )
        session.add(secret)
        session.flush()
        return secret

    def get_secret_by_id(self, session: Session, secret_id: str) -> Secret | None:
        return session.scalar(select(Secret).where(Secret.id == secret_id))

    def get_secret_by_name(
        self,
        session: Session,
        tenant_id: str,
        name: str,
        project_id: str | None = None,
        environment_id: str | None = None,
    ) -> Secret | None:
        stmt = select(Secret).where(Secret.tenant_id == tenant_id, Secret.name == name)
        if project_id:
            stmt = stmt.where(or_(Secret.project_id == project_id, Secret.project_id.is_(None)))
        if environment_id:
            stmt = stmt.where(
                or_(Secret.environment_id == environment_id, Secret.environment_id.is_(None))
            )
        return session.scalar(stmt.order_by(Secret.scope.desc()))

    def list_secrets(
        self,
        session: Session,
        tenant_id: str,
        project_id: str | None = None,
        environment_id: str | None = None,
        scope: str | None = None,
        secret_type: str | None = None,
        search: str | None = None,
    ) -> list[Secret]:
        stmt = select(Secret).where(Secret.tenant_id == tenant_id)

        if project_id:
            stmt = stmt.where(or_(Secret.project_id == project_id, Secret.scope == "organization"))
        if environment_id:
            stmt = stmt.where(
                or_(
                    Secret.environment_id == environment_id,
                    Secret.scope.in_(["organization", "project"]),
                )
            )
        if scope:
            stmt = stmt.where(Secret.scope == scope)
        if secret_type:
            stmt = stmt.where(Secret.secret_type == secret_type)
        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(Secret.name.ilike(search_pattern), Secret.description.ilike(search_pattern))
            )

        return list(session.scalars(stmt.order_by(Secret.updated_at.desc())).all())

    def update_secret_metadata(
        self,
        session: Session,
        secret_id: str,
        modified_by: str,
        description: str | None = None,
        expiration_date: datetime | None = None,
        rotation_interval_days: int | None = None,
        status: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> Secret | None:
        secret = self.get_secret_by_id(session, secret_id)
        if not secret:
            return None
        if description is not None:
            secret.description = description
        if expiration_date is not None:
            secret.expiration_date = expiration_date
        if rotation_interval_days is not None:
            secret.rotation_interval_days = rotation_interval_days
        if status is not None:
            secret.status = status
        if metadata_json is not None:
            secret.metadata_json = metadata_json
        secret.modified_by = modified_by
        secret.updated_at = datetime.now(UTC)
        session.flush()
        return secret

    def delete_secret(self, session: Session, secret_id: str) -> bool:
        secret = self.get_secret_by_id(session, secret_id)
        if not secret:
            return False
        session.delete(secret)
        session.flush()
        return True

    # --- Version CRUD ---
    def create_version(
        self,
        session: Session,
        secret_id: str,
        version_num: int,
        created_by: str,
        provider_version_ref: str | None = None,
        encrypted_value: str | None = None,
        encryption_metadata: dict[str, Any] | None = None,
        comment: str = "",
    ) -> SecretVersion:
        ver = SecretVersion(
            secret_id=secret_id,
            version_num=version_num,
            provider_version_ref=provider_version_ref,
            encrypted_value=encrypted_value,
            encryption_metadata=encryption_metadata or {},
            created_by=created_by,
            comment=comment,
        )
        session.add(ver)
        session.flush()

        secret = self.get_secret_by_id(session, secret_id)
        if secret:
            secret.current_version_id = ver.id
            secret.modified_by = created_by
            secret.updated_at = datetime.now(UTC)
            session.flush()

        return ver

    def get_version(self, session: Session, version_id: str) -> SecretVersion | None:
        return session.scalar(select(SecretVersion).where(SecretVersion.id == version_id))

    def get_current_version(self, session: Session, secret_id: str) -> SecretVersion | None:
        secret = self.get_secret_by_id(session, secret_id)
        if not secret or not secret.current_version_id:
            return session.scalar(
                select(SecretVersion)
                .where(SecretVersion.secret_id == secret_id)
                .order_by(SecretVersion.version_num.desc())
            )
        return self.get_version(session, secret.current_version_id)

    def list_versions(self, session: Session, secret_id: str) -> list[SecretVersion]:
        return list(
            session.scalars(
                select(SecretVersion)
                .where(SecretVersion.secret_id == secret_id)
                .order_by(SecretVersion.version_num.desc())
            ).all()
        )

    # --- Assignment CRUD ---
    def assign_entity(
        self,
        session: Session,
        secret_id: str,
        entity_type: str,
        entity_id: str,
        entity_name: str,
        assigned_by: str,
    ) -> SecretAssignment:
        existing = session.scalar(
            select(SecretAssignment).where(
                SecretAssignment.secret_id == secret_id,
                SecretAssignment.entity_type == entity_type,
                SecretAssignment.entity_id == entity_id,
            )
        )
        if existing:
            return existing

        assignment = SecretAssignment(
            secret_id=secret_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            assigned_by=assigned_by,
        )
        session.add(assignment)
        session.flush()
        return assignment

    def revoke_assignment(self, session: Session, assignment_id: str) -> bool:
        asgn = session.scalar(select(SecretAssignment).where(SecretAssignment.id == assignment_id))
        if not asgn:
            return False
        session.delete(asgn)
        session.flush()
        return True

    def list_assignments(self, session: Session, secret_id: str) -> list[SecretAssignment]:
        return list(
            session.scalars(
                select(SecretAssignment)
                .where(SecretAssignment.secret_id == secret_id)
                .order_by(SecretAssignment.entity_name)
            ).all()
        )

    def is_entity_assigned(
        self, session: Session, secret_id: str, entity_type: str, entity_id: str
    ) -> bool:
        count = session.scalar(
            select(SecretAssignment).where(
                SecretAssignment.secret_id == secret_id,
                SecretAssignment.entity_type == entity_type,
                SecretAssignment.entity_id == entity_id,
            )
        )
        return count is not None
