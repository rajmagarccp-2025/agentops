import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from platform_api.identity_models import (
    AuditChainHead,
    AuditLog,
    AuditLogArchive,
    EnvironmentMember,
    EnvironmentModel,
    Invitation,
    Membership,
    Project,
    ProjectMember,
    Role,
    Tenant,
    User,
    UserTenantRole,
)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${key.hex()}"


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed or "$" not in hashed:
        return False
    try:
        salt, key_hex = hashed.split("$", 1)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
        return secrets.compare_digest(key.hex(), key_hex)
    except Exception:
        return False


DOMAIN_READ_PERMISSIONS = {
    "inventory:read",
    "inventory.read",
    "incidents:read",
    "incidents.read",
    "finops:read",
    "finops.read",
    "changes:read",
    "changes.read",
    "remediation:read",
    "remediation.read",
    "tools:read",
    "tools.read",
    "rag:read",
    "rag.read",
    "agents:read",
    "agents.read",
    "llm:read",
    "llm.read",
    "learning:read",
    "learning.read",
    "cloud:read",
    "cloud.read",
    "observability:read",
    "observability.read",
}

DOMAIN_WRITE_PERMISSIONS = DOMAIN_READ_PERMISSIONS | {
    "incidents:write",
    "incidents.write",
    "incidents:investigate",
    "incidents.investigate",
    "finops:write",
    "finops.write",
    "changes:write",
    "changes.write",
    "remediation:execute",
    "remediation.execute",
    "remediation:verify",
    "remediation.verify",
    "rag:write",
    "rag.write",
    "agents:run",
    "agents.run",
    "llm:invoke",
    "llm.invoke",
    "llm:write",
    "llm.write",
    "llm:evaluate",
    "llm.evaluate",
    "learning:write",
    "learning.write",
    "cloud:manage",
    "cloud.manage",
}

DOMAIN_ADMIN_PERMISSIONS = DOMAIN_WRITE_PERMISSIONS | {
    "approvals:read",
    "approvals.read",
    "approvals:approve",
    "approvals.approve",
    "security:read",
    "security.read",
    "security:write",
    "security.write",
    "security:investigate",
    "security.investigate",
    "governance:manage",
    "governance.manage",
}

SECRETS_READ_PERMISSIONS = {
    "secrets:metadata:read",
    "secrets.metadata.read",
    "secrets:metadata_read",
    "secrets.metadata_read",
    "secrets:read",
    "secrets.read",
    "secrets:audit:read",
    "secrets.audit.read",
}

SECRETS_WRITE_PERMISSIONS = SECRETS_READ_PERMISSIONS | {
    "secrets:create",
    "secrets.create",
    "secrets:update",
    "secrets.update",
    "secrets:version:create",
    "secrets.version.create",
    "secrets:rotate",
    "secrets.rotate",
    "secrets:revoke",
    "secrets.revoke",
    "secrets:assign",
    "secrets.assign",
    "secrets:unassign",
    "secrets.unassign",
    "secrets:scope:update",
    "secrets.scope.update",
}

SECRETS_ADMIN_PERMISSIONS = SECRETS_WRITE_PERMISSIONS | {
    "secrets:value:read",
    "secrets.value.read",
    "secrets:delete",
    "secrets.delete",
    "secrets:revoke",
    "secrets.revoke",
    "secret_providers:configure",
    "secret_providers.configure",
    "secret_policies:manage",
    "secret_policies.manage",
}

DOMAIN_READ_PERMISSIONS = DOMAIN_READ_PERMISSIONS | SECRETS_READ_PERMISSIONS
DOMAIN_WRITE_PERMISSIONS = DOMAIN_WRITE_PERMISSIONS | SECRETS_WRITE_PERMISSIONS
DOMAIN_ADMIN_PERMISSIONS = DOMAIN_ADMIN_PERMISSIONS | SECRETS_ADMIN_PERMISSIONS

ROLE_PERMISSIONS_MAP: dict[str, set[str]] = {
    "ADMIN": DOMAIN_ADMIN_PERMISSIONS
    | SECRETS_ADMIN_PERMISSIONS
    | {
        "organization:read",
        "organization:write",
        "organization:update",
        "organization:delete",
        "member:read",
        "member:invite",
        "member:remove",
        "member:role_change",
        "project:read",
        "project:create",
        "project:update",
        "project:delete",
        "project:member_manage",
        "environment:read",
        "environment:create",
        "environment:update",
        "environment:delete",
        "environment:member_manage",
        "data:read",
        "data:write",
        "ai:read",
        "ai:query",
        "ai:execute",
        "ai:admin",
        "audit:read",
        "observability:read",
        "observability.read",
        "cloud:read",
        "cloud.read",
        "cloud:manage",
        "cloud.manage",
        "organization.read",
        "organization.write",
        "organization.update",
        "organization.delete",
        "member.read",
        "member.invite",
        "member.remove",
        "member.role_change",
        "project.read",
        "project.create",
        "project.update",
        "project.delete",
        "project.member_manage",
        "environment.read",
        "environment.create",
        "environment.update",
        "environment.delete",
        "environment.member_manage",
        "data.read",
        "data.write",
        "ai.read",
        "ai.query",
        "ai.execute",
        "ai.admin",
        "audit.read",
    },
    "WRITE": DOMAIN_WRITE_PERMISSIONS
    | SECRETS_WRITE_PERMISSIONS
    | {
        "organization:read",
        "organization.read",
        "project:read",
        "project.read",
        "environment:read",
        "environment.read",
        "data:read",
        "data.read",
        "data:write",
        "data.write",
        "ai:read",
        "ai.read",
        "ai:query",
        "ai.query",
        "ai:execute",
        "ai.execute",
        "observability:read",
        "observability.read",
        "cloud:read",
        "cloud.read",
    },
    "READ": DOMAIN_READ_PERMISSIONS
    | SECRETS_READ_PERMISSIONS
    | {
        "organization:read",
        "organization.read",
        "project:read",
        "project.read",
        "environment:read",
        "environment.read",
        "data:read",
        "data.read",
        "ai:read",
        "ai.read",
        "observability:read",
        "observability.read",
        "cloud:read",
        "cloud.read",
    },
    "OWNER": DOMAIN_ADMIN_PERMISSIONS
    | SECRETS_ADMIN_PERMISSIONS
    | {
        "organization:read",
        "organization:write",
        "organization:update",
        "organization:delete",
        "member:read",
        "member:invite",
        "member:remove",
        "member:role_change",
        "project:read",
        "project:create",
        "project:update",
        "project:delete",
        "project.member_manage",
        "environment:read",
        "environment:create",
        "environment:update",
        "environment:delete",
        "environment.member_manage",
        "data:read",
        "data:write",
        "ai:read",
        "ai:query",
        "ai:execute",
        "ai:admin",
        "audit:read",
        "organization:transfer_ownership",
        "observability:read",
        "observability.read",
        "cloud:read",
        "cloud.read",
        "cloud:manage",
        "cloud.manage",
        "organization.read",
        "organization.write",
        "organization.update",
        "organization.delete",
        "member.read",
        "member.invite",
        "member.remove",
        "member.role_change",
        "project.read",
        "project.create",
        "project.update",
        "project.delete",
        "environment.read",
        "environment.create",
        "environment.update",
        "environment.delete",
        "data.read",
        "data.write",
        "ai.read",
        "ai.query",
        "ai.execute",
        "ai.admin",
        "audit.read",
    },
}

# Role synonyms and hierarchy mappings
ROLE_PERMISSIONS_MAP["MEMBER"] = ROLE_PERMISSIONS_MAP["WRITE"]
ROLE_PERMISSIONS_MAP["OPERATOR"] = ROLE_PERMISSIONS_MAP["WRITE"]
ROLE_PERMISSIONS_MAP["DEVELOPER"] = ROLE_PERMISSIONS_MAP["WRITE"]
ROLE_PERMISSIONS_MAP["SECRET_EDITOR"] = ROLE_PERMISSIONS_MAP["WRITE"]
ROLE_PERMISSIONS_MAP["VIEWER"] = ROLE_PERMISSIONS_MAP["READ"]
ROLE_PERMISSIONS_MAP["READER"] = ROLE_PERMISSIONS_MAP["READ"]
ROLE_PERMISSIONS_MAP["SECRET_VIEWER"] = ROLE_PERMISSIONS_MAP["READ"]
ROLE_PERMISSIONS_MAP["SECRET_OWNER"] = ROLE_PERMISSIONS_MAP["ADMIN"]
ROLE_PERMISSIONS_MAP["RUNTIME_CONSUMER"] = {"secrets.runtime.resolve", "secrets:runtime:resolve"}
ROLE_PERMISSIONS_MAP["VIEWER"] = ROLE_PERMISSIONS_MAP["READ"]
ROLE_PERMISSIONS_MAP["PLATFORM-ADMIN"] = ROLE_PERMISSIONS_MAP["ADMIN"]
ROLE_PERMISSIONS_MAP["PROJECT ADMIN"] = DOMAIN_READ_PERMISSIONS | {
    "project:read",
    "project:update",
    "project:member_manage",
    "environment:read",
    "environment:create",
    "environment:update",
    "environment:delete",
    "environment:member_manage",
    "data:read",
    "data:write",
    "ai:read",
    "ai:query",
    "rag:write",
    "agents:run",
    "cloud:manage",
}
ROLE_PERMISSIONS_MAP["PROJECT_ADMIN"] = ROLE_PERMISSIONS_MAP["PROJECT ADMIN"]
ROLE_PERMISSIONS_MAP["PROJECT MEMBER"] = ROLE_PERMISSIONS_MAP["WRITE"]
ROLE_PERMISSIONS_MAP["PROJECT_MEMBER"] = ROLE_PERMISSIONS_MAP["WRITE"]
ROLE_PERMISSIONS_MAP["PROJECT VIEWER"] = ROLE_PERMISSIONS_MAP["READ"]
ROLE_PERMISSIONS_MAP["PROJECT_VIEWER"] = ROLE_PERMISSIONS_MAP["READ"]
ROLE_PERMISSIONS_MAP["ENVIRONMENT ADMIN"] = DOMAIN_READ_PERMISSIONS | {
    "project:read",
    "environment:read",
    "environment:update",
    "environment:delete",
    "environment:member_manage",
    "data:read",
    "data:write",
    "ai:read",
    "ai:query",
    "rag:write",
    "agents:run",
    "cloud:manage",
}
ROLE_PERMISSIONS_MAP["ENVIRONMENT_ADMIN"] = ROLE_PERMISSIONS_MAP["ENVIRONMENT ADMIN"]
ROLE_PERMISSIONS_MAP["ENVIRONMENT OPERATOR"] = ROLE_PERMISSIONS_MAP["WRITE"]
ROLE_PERMISSIONS_MAP["ENVIRONMENT_OPERATOR"] = ROLE_PERMISSIONS_MAP["WRITE"]
ROLE_PERMISSIONS_MAP["ENVIRONMENT VIEWER"] = ROLE_PERMISSIONS_MAP["READ"]
ROLE_PERMISSIONS_MAP["ENVIRONMENT_VIEWER"] = ROLE_PERMISSIONS_MAP["READ"]


class TenantRepository:
    def create_tenant(
        self,
        session: Session,
        name: str,
        slug: str,
        description: str = "",
        created_by: str | None = None,
        logo_url: str | None = None,
    ) -> Tenant:
        tenant = Tenant(
            name=name,
            slug=slug,
            description=description,
            created_by=created_by,
            logo_url=logo_url,
        )
        session.add(tenant)
        session.flush()
        return tenant

    def get_tenant_by_id(self, session: Session, tenant_id: str) -> Tenant | None:
        return session.scalar(select(Tenant).where(Tenant.id == tenant_id))

    def get_tenant_by_slug(self, session: Session, slug: str) -> Tenant | None:
        return session.scalar(select(Tenant).where(Tenant.slug == slug))

    def list_user_tenants(self, session: Session, user_id: str) -> list[Tenant]:
        stmt = (
            select(Tenant)
            .join(Membership, Membership.tenant_id == Tenant.id)
            .where(Membership.user_id == user_id, Tenant.active.is_(True))
            .order_by(Tenant.name)
        )
        return list(session.scalars(stmt).all())

    def update_tenant(
        self,
        session: Session,
        tenant_id: str,
        name: str | None = None,
        description: str | None = None,
        logo_url: str | None = None,
    ) -> Tenant | None:
        tenant = self.get_tenant_by_id(session, tenant_id)
        if not tenant:
            return None
        if name is not None:
            tenant.name = name
        if description is not None:
            tenant.description = description
        if logo_url is not None:
            tenant.logo_url = logo_url
        session.flush()
        return tenant

    def delete_tenant(self, session: Session, tenant_id: str) -> bool:
        tenant = self.get_tenant_by_id(session, tenant_id)
        if not tenant:
            return False
        session.delete(tenant)
        session.flush()
        return True


class ProjectRepository:
    def create_project(
        self,
        session: Session,
        tenant_id: str,
        name: str,
        slug: str,
        description: str = "",
        created_by: str | None = None,
    ) -> Project:
        project = Project(tenant_id=tenant_id, name=name, slug=slug, description=description)
        session.add(project)
        session.flush()
        return project

    def get_project_by_id(self, session: Session, project_id: str) -> Project | None:
        return session.scalar(select(Project).where(Project.id == project_id))

    def get_project_by_slug(self, session: Session, tenant_id: str, slug: str) -> Project | None:
        return session.scalar(
            select(Project).where(Project.tenant_id == tenant_id, Project.slug == slug)
        )

    def list_projects(self, session: Session, tenant_id: str) -> list[Project]:
        return list(
            session.scalars(
                select(Project).where(Project.tenant_id == tenant_id).order_by(Project.name)
            ).all()
        )

    def list_user_projects(
        self, session: Session, tenant_id: str, user_id: str, is_org_admin: bool = False
    ) -> list[Project]:
        if is_org_admin:
            return self.list_projects(session, tenant_id)
        stmt = (
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(Project.tenant_id == tenant_id, ProjectMember.user_id == user_id)
            .order_by(Project.name)
        )
        return list(session.scalars(stmt).all())

    def update_project(
        self,
        session: Session,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> Project | None:
        project = self.get_project_by_id(session, project_id)
        if not project:
            return None
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        session.flush()
        return project

    def delete_project(self, session: Session, project_id: str) -> bool:
        project = self.get_project_by_id(session, project_id)
        if not project:
            return False
        session.delete(project)
        session.flush()
        return True


class EnvironmentRepository:
    def create_environment(
        self,
        session: Session,
        tenant_id: str,
        project_id: str,
        name: str,
        slug: str,
        env_type: str = "Development",
        description: str = "",
        created_by: str | None = None,
    ) -> EnvironmentModel:
        env = EnvironmentModel(
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            slug=slug,
            type=env_type,
            description=description,
        )
        session.add(env)
        session.flush()
        return env

    def get_environment_by_id(
        self, session: Session, environment_id: str
    ) -> EnvironmentModel | None:
        return session.scalar(select(EnvironmentModel).where(EnvironmentModel.id == environment_id))

    def list_environments(
        self, session: Session, tenant_id: str, project_id: str
    ) -> list[EnvironmentModel]:
        return list(
            session.scalars(
                select(EnvironmentModel)
                .where(
                    EnvironmentModel.tenant_id == tenant_id,
                    EnvironmentModel.project_id == project_id,
                )
                .order_by(EnvironmentModel.name)
            ).all()
        )

    def list_user_environments(
        self,
        session: Session,
        tenant_id: str,
        project_id: str,
        user_id: str,
        is_proj_admin: bool = False,
    ) -> list[EnvironmentModel]:
        if is_proj_admin:
            return self.list_environments(session, tenant_id, project_id)
        stmt = (
            select(EnvironmentModel)
            .join(EnvironmentMember, EnvironmentMember.environment_id == EnvironmentModel.id)
            .where(
                EnvironmentModel.tenant_id == tenant_id,
                EnvironmentModel.project_id == project_id,
                EnvironmentMember.user_id == user_id,
            )
            .order_by(EnvironmentModel.name)
        )
        return list(session.scalars(stmt).all())

    def update_environment(
        self,
        session: Session,
        environment_id: str,
        name: str | None = None,
        env_type: str | None = None,
        description: str | None = None,
    ) -> EnvironmentModel | None:
        env = self.get_environment_by_id(session, environment_id)
        if not env:
            return None
        if name is not None:
            env.name = name
        if env_type is not None:
            env.type = env_type
        if description is not None:
            env.description = description
        session.flush()
        return env

    def delete_environment(self, session: Session, environment_id: str) -> bool:
        env = self.get_environment_by_id(session, environment_id)
        if not env:
            return False
        session.delete(env)
        session.flush()
        return True


class MembershipRepository:
    def get_user_by_subject(self, session: Session, subject: str) -> User | None:
        return session.scalar(select(User).where(User.subject == subject))

    def get_user_by_email(self, session: Session, email: str) -> User | None:
        return session.scalar(select(User).where(User.email.ilike(email)))

    def get_user_by_id(self, session: Session, user_id: str) -> User | None:
        return session.scalar(select(User).where(User.id == user_id))

    def create_or_sync_user(
        self, session: Session, subject: str, email: str, display_name: str
    ) -> User:
        user = self.get_user_by_subject(session, subject)
        if not user:
            # Check by email in case of subject migration
            user = self.get_user_by_email(session, email)
            if user:
                user.subject = subject
                user.display_name = display_name
            else:
                user = User(subject=subject, email=email, display_name=display_name)
                session.add(user)
        else:
            user.email = email
            user.display_name = display_name
        session.flush()
        return user

    def create_user_with_password(
        self, session: Session, display_name: str, email: str, password: str
    ) -> User:
        clean_email = email.lower().strip()
        existing = self.get_user_by_email(session, clean_email)
        if existing:
            raise ValueError(f"User with email {clean_email} already exists")
        pw_hash = hash_password(password)
        uid = str(uuid4())
        user = User(
            id=uid,
            subject=uid,
            email=clean_email,
            display_name=display_name.strip(),
            password_hash=pw_hash,
            active=True,
        )
        session.add(user)
        session.flush()
        return user

    def authenticate_user(self, session: Session, email: str, password: str) -> User | None:
        clean_email = email.lower().strip()
        user = self.get_user_by_email(session, clean_email)
        if not user:
            return None
        # Verify stored password hash
        if user.password_hash:
            if verify_password(password, user.password_hash):
                return user
            return None
        # Seeded Keycloak test users without password_hash in DB
        demo_passwords = {
            "alex.rivera@enterprise.com": "EnterprisePassword123!",
            "operator@enterprise.com": "OperatorPassword123!",
        }
        if clean_email in demo_passwords and demo_passwords[clean_email] == password:
            user.password_hash = hash_password(password)
            session.flush()
            return user
        return None

    def get_role_by_name(self, session: Session, role_name: str) -> Role:
        role = session.scalar(select(Role).where(Role.name == role_name.upper()))
        if not role:
            role = Role(name=role_name.upper(), description=f"{role_name} role")
            session.add(role)
            session.flush()
        return role

    def add_organization_member(
        self, session: Session, tenant_id: str, user_id: str, role_name: str, is_owner: bool = False
    ) -> Membership:
        role = self.get_role_by_name(session, role_name)
        existing = session.scalar(
            select(Membership).where(
                Membership.tenant_id == tenant_id, Membership.user_id == user_id
            )
        )
        if existing:
            existing.role_id = role.id
            if is_owner:
                existing.is_owner = True
            session.flush()
            return existing

        membership = Membership(
            tenant_id=tenant_id,
            user_id=user_id,
            role_id=role.id,
            is_owner=is_owner,
        )
        session.add(membership)
        session.flush()
        return membership

    def get_organization_membership(
        self, session: Session, tenant_id: str, user_id: str
    ) -> tuple[Membership, Role] | None:
        row = session.execute(
            select(Membership, Role)
            .join(Role, Membership.role_id == Role.id)
            .where(Membership.tenant_id == tenant_id, Membership.user_id == user_id)
        ).first()
        if not row:
            return None
        return row[0], row[1]

    def list_organization_members(self, session: Session, tenant_id: str) -> list[dict[str, Any]]:
        rows = session.execute(
            select(Membership, User, Role)
            .join(User, Membership.user_id == User.id)
            .join(Role, Membership.role_id == Role.id)
            .where(Membership.tenant_id == tenant_id)
            .order_by(User.display_name)
        ).all()
        return [
            {
                "membership_id": m.id,
                "user_id": u.id,
                "email": u.email,
                "name": u.display_name,
                "role": r.name,
                "is_owner": m.is_owner,
                "created_at": m.created_at.isoformat(),
            }
            for m, u, r in rows
        ]

    def remove_organization_member(self, session: Session, tenant_id: str, user_id: str) -> bool:
        stmt = delete(Membership).where(
            Membership.tenant_id == tenant_id, Membership.user_id == user_id
        )
        res = session.execute(stmt)
        session.flush()
        return res.rowcount > 0

    def add_project_member(
        self, session: Session, project_id: str, user_id: str, role_name: str
    ) -> ProjectMember:
        role = self.get_role_by_name(session, role_name)
        existing = session.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
            )
        )
        if existing:
            existing.role_id = role.id
            session.flush()
            return existing

        pm = ProjectMember(project_id=project_id, user_id=user_id, role_id=role.id)
        session.add(pm)
        session.flush()
        return pm

    def get_project_membership(
        self, session: Session, project_id: str, user_id: str
    ) -> tuple[ProjectMember, Role] | None:
        row = session.execute(
            select(ProjectMember, Role)
            .join(Role, ProjectMember.role_id == Role.id)
            .where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        ).first()
        if not row:
            return None
        return row[0], row[1]

    def list_project_members(self, session: Session, project_id: str) -> list[dict[str, Any]]:
        rows = session.execute(
            select(ProjectMember, User, Role)
            .join(User, ProjectMember.user_id == User.id)
            .join(Role, ProjectMember.role_id == Role.id)
            .where(ProjectMember.project_id == project_id)
            .order_by(User.display_name)
        ).all()
        return [
            {
                "membership_id": pm.id,
                "user_id": u.id,
                "email": u.email,
                "name": u.display_name,
                "role": r.name,
                "created_at": pm.created_at.isoformat(),
            }
            for pm, u, r in rows
        ]

    def remove_project_member(self, session: Session, project_id: str, user_id: str) -> bool:
        stmt = delete(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
        res = session.execute(stmt)
        session.flush()
        return res.rowcount > 0

    def add_environment_member(
        self, session: Session, environment_id: str, user_id: str, role_name: str
    ) -> EnvironmentMember:
        role = self.get_role_by_name(session, role_name)
        existing = session.scalar(
            select(EnvironmentMember).where(
                EnvironmentMember.environment_id == environment_id,
                EnvironmentMember.user_id == user_id,
            )
        )
        if existing:
            existing.role_id = role.id
            session.flush()
            return existing

        em = EnvironmentMember(environment_id=environment_id, user_id=user_id, role_id=role.id)
        session.add(em)
        session.flush()
        return em

    def get_environment_membership(
        self, session: Session, environment_id: str, user_id: str
    ) -> tuple[EnvironmentMember, Role] | None:
        row = session.execute(
            select(EnvironmentMember, Role)
            .join(Role, EnvironmentMember.role_id == Role.id)
            .where(
                EnvironmentMember.environment_id == environment_id,
                EnvironmentMember.user_id == user_id,
            )
        ).first()
        if not row:
            return None
        return row[0], row[1]

    def list_environment_members(
        self, session: Session, environment_id: str
    ) -> list[dict[str, Any]]:
        rows = session.execute(
            select(EnvironmentMember, User, Role)
            .join(User, EnvironmentMember.user_id == User.id)
            .join(Role, EnvironmentMember.role_id == Role.id)
            .where(EnvironmentMember.environment_id == environment_id)
            .order_by(User.display_name)
        ).all()
        return [
            {
                "membership_id": em.id,
                "user_id": u.id,
                "email": u.email,
                "name": u.display_name,
                "role": r.name,
                "created_at": em.created_at.isoformat(),
            }
            for em, u, r in rows
        ]

    def remove_environment_member(
        self, session: Session, environment_id: str, user_id: str
    ) -> bool:
        stmt = delete(EnvironmentMember).where(
            EnvironmentMember.environment_id == environment_id, EnvironmentMember.user_id == user_id
        )
        res = session.execute(stmt)
        session.flush()
        return res.rowcount > 0

    def get_tenant_memberships_for_user(
        self, session: Session, user_id: str
    ) -> list[dict[str, Any]]:
        # Fetch from UserTenantRole or Membership tables
        user_roles = session.execute(
            select(UserTenantRole.tenant_id, Role.name)
            .join(Role, UserTenantRole.role_id == Role.id)
            .where(UserTenantRole.user_id == user_id)
        ).all()
        result: dict[str, list[str]] = {}
        for tenant_id, role_name in user_roles:
            result.setdefault(tenant_id, []).append(role_name)

        memberships = session.execute(
            select(Membership.tenant_id, Role.name)
            .join(Role, Membership.role_id == Role.id)
            .where(Membership.user_id == user_id)
        ).all()
        for tenant_id, role_name in memberships:
            roles = result.setdefault(tenant_id, [])
            if role_name not in roles:
                roles.append(role_name)

        return [{"tenant_id": t_id, "roles": r} for t_id, r in result.items()]


class InvitationRepository:
    def create_invitation(
        self,
        session: Session,
        email: str,
        organization_id: str,
        role_name: str,
        created_by: str,
        project_id: str | None = None,
        environment_id: str | None = None,
        expires_days: int = 7,
    ) -> Invitation:
        role = MembershipRepository().get_role_by_name(session, role_name)
        token = secrets.token_urlsafe(32)
        invitation = Invitation(
            email=email.lower().strip(),
            organization_id=organization_id,
            project_id=project_id,
            environment_id=environment_id,
            role_id=role.id,
            token=token,
            status="pending",
            created_by=created_by,
            expires_at=datetime.now(UTC) + timedelta(days=expires_days),
        )
        session.add(invitation)
        session.flush()
        return invitation

    def get_by_token(self, session: Session, token: str) -> Invitation | None:
        return session.scalar(select(Invitation).where(Invitation.token == token))

    def list_pending_for_email(self, session: Session, email: str) -> list[Invitation]:
        now = datetime.now(UTC)
        stmt = (
            select(Invitation)
            .where(
                Invitation.email.ilike(email.strip()),
                Invitation.status == "pending",
                Invitation.expires_at > now,
            )
            .order_by(Invitation.created_at.desc())
        )
        return list(session.scalars(stmt).all())

    def list_organization_invitations(
        self, session: Session, organization_id: str
    ) -> list[dict[str, Any]]:
        rows = session.execute(
            select(Invitation, Role)
            .join(Role, Invitation.role_id == Role.id)
            .where(Invitation.organization_id == organization_id)
            .order_by(Invitation.created_at.desc())
        ).all()
        now = datetime.now(UTC)
        result = []
        for inv, r in rows:
            status = inv.status
            exp = inv.expires_at if inv.expires_at.tzinfo else inv.expires_at.replace(tzinfo=UTC)
            if status == "pending" and exp < now:
                status = "expired"
            result.append(
                {
                    "id": inv.id,
                    "email": inv.email,
                    "organization_id": inv.organization_id,
                    "project_id": inv.project_id,
                    "environment_id": inv.environment_id,
                    "role": r.name,
                    "status": status,
                    "token": inv.token,
                    "created_by": inv.created_by,
                    "created_at": inv.created_at.isoformat(),
                    "expires_at": inv.expires_at.isoformat(),
                }
            )
        return result

    def accept_invitation(self, session: Session, token: str, user: User) -> tuple[Invitation, str]:
        invitation = self.get_by_token(session, token)
        if not invitation:
            return None, "Invitation not found"
        if invitation.status == "accepted":
            return invitation, "This invitation has already been used."
        exp = (
            invitation.expires_at
            if invitation.expires_at.tzinfo
            else invitation.expires_at.replace(tzinfo=UTC)
        )
        if exp < datetime.now(UTC) or invitation.status == "expired":
            return invitation, "This invitation has expired."
        if invitation.status != "pending":
            return invitation, f"Invitation status is {invitation.status}"

        # Assign organization membership
        role = session.scalar(select(Role).where(Role.id == invitation.role_id))
        role_name = role.name if role else "READ"
        mem_repo = MembershipRepository()
        mem_repo.add_organization_member(session, invitation.organization_id, user.id, role_name)

        # If project_id is specified, assign project membership
        if invitation.project_id:
            mem_repo.add_project_member(session, invitation.project_id, user.id, role_name)

        # If environment_id is specified, assign environment membership
        if invitation.environment_id:
            mem_repo.add_environment_member(session, invitation.environment_id, user.id, role_name)

        invitation.status = "accepted"
        invitation.accepted_at = datetime.now(UTC)
        session.flush()
        return invitation, "success"


class AuditLogRepository:
    def record_event(
        self,
        session: Session,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: str,
        organization_id: str | None = None,
        project_id: str | None = None,
        environment_id: str | None = None,
        actor_email: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        created_at = datetime.now(UTC)
        chain_id = organization_id or "__global__"
        head_insert = {
            "chain_id": chain_id,
            "sequence_number": 0,
            "event_hash": "0" * 64,
        }
        dialect = session.get_bind().dialect.name
        if dialect == "postgresql":
            session.execute(
                pg_insert(AuditChainHead)
                .values(**head_insert)
                .on_conflict_do_nothing(index_elements=["chain_id"])
            )
        elif dialect == "sqlite":
            session.execute(
                sqlite_insert(AuditChainHead)
                .values(**head_insert)
                .on_conflict_do_nothing(index_elements=["chain_id"])
            )
        else:
            if session.get(AuditChainHead, chain_id) is None:
                session.add(AuditChainHead(**head_insert))
                session.flush()

        head = session.scalar(
            select(AuditChainHead)
            .where(AuditChainHead.chain_id == chain_id)
            .with_for_update()
        )
        if head is None:
            raise RuntimeError(f"Could not acquire audit chain head for {chain_id}")
        sequence_number = head.sequence_number + 1
        previous_hash = head.event_hash
        event_data = {
            "actor": actor,
            "actor_email": actor_email,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "organization_id": organization_id,
            "project_id": project_id,
            "environment_id": environment_id,
            "details": details or {},
            "created_at": self._canonical_datetime(created_at),
            "sequence_number": sequence_number,
        }
        event_hash = self._event_hash(event_data, previous_hash)
        log = AuditLog(
            actor=actor,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            organization_id=organization_id,
            project_id=project_id,
            environment_id=environment_id,
            details=details or {},
            sequence_number=sequence_number,
            previous_hash=previous_hash,
            event_hash=event_hash,
            created_at=created_at,
        )
        session.add(log)
        session.flush()
        head.sequence_number = sequence_number
        head.event_hash = event_hash
        return log

    @staticmethod
    def _event_hash(event_data: dict[str, Any], previous_hash: str) -> str:
        canonical = json.dumps(
            {"previous_hash": previous_hash, **event_data},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _canonical_datetime(value: datetime) -> str:
        normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return normalized.isoformat()

    def verify_chain(self, session: Session, organization_id: str | None) -> dict[str, Any]:
        chain_id = organization_id or "__global__"
        rows = session.scalars(
            select(AuditLog)
            .where(AuditLog.organization_id == organization_id)
            .order_by(AuditLog.sequence_number.asc())
        ).all()
        previous_hash = "0" * 64
        expected_sequence = 1
        for row in rows:
            if row.sequence_number != expected_sequence or row.previous_hash != previous_hash:
                return {
                    "valid": False,
                    "chain_id": chain_id,
                    "verified_events": expected_sequence - 1,
                    "failed_event_id": row.id,
                }
            event_data = {
                "actor": row.actor,
                "actor_email": row.actor_email,
                "action": row.action,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "organization_id": row.organization_id,
                "project_id": row.project_id,
                "environment_id": row.environment_id,
                "details": row.details,
                "created_at": self._canonical_datetime(row.created_at),
                "sequence_number": row.sequence_number,
            }
            calculated = self._event_hash(event_data, previous_hash)
            if row.event_hash != calculated:
                return {
                    "valid": False,
                    "chain_id": chain_id,
                    "verified_events": expected_sequence - 1,
                    "failed_event_id": row.id,
                }
            previous_hash = calculated
            expected_sequence += 1
        archived_rows = session.execute(
            select(AuditLogArchive.id, AuditLog.event_hash, AuditLogArchive.event_hash)
            .outerjoin(AuditLog, AuditLog.id == AuditLogArchive.id)
            .where(AuditLogArchive.organization_id == organization_id)
        ).all()
        for archive_id, source_hash, archive_hash in archived_rows:
            if source_hash is None or source_hash != archive_hash:
                return {
                    "valid": False,
                    "chain_id": chain_id,
                    "verified_events": expected_sequence - 1,
                    "failed_event_id": archive_id,
                    "failure": "archive_mismatch",
                }
        head = session.get(AuditChainHead, chain_id)
        head_matches = (
            (head is None and not rows)
            or (
                head is not None
                and head.sequence_number == expected_sequence - 1
                and head.event_hash == previous_hash
            )
        )
        return {
            "valid": head_matches,
            "chain_id": chain_id,
            "verified_events": expected_sequence - 1,
            "failed_event_id": None if head_matches else "chain_head",
        }

    def archive_before(self, session: Session, cutoff: datetime, batch_size: int = 500) -> int:
        rows = session.scalars(
            select(AuditLog)
            .where(
                AuditLog.created_at < cutoff,
                ~select(AuditLogArchive.id)
                .where(AuditLogArchive.id == AuditLog.id)
                .exists(),
            )
            .order_by(AuditLog.created_at.asc())
            .limit(batch_size)
        ).all()
        archived_at = datetime.now(UTC)
        for row in rows:
            session.add(
                AuditLogArchive(
                    id=row.id,
                    actor=row.actor,
                    actor_email=row.actor_email,
                    action=row.action,
                    resource_type=row.resource_type,
                    resource_id=row.resource_id,
                    organization_id=row.organization_id,
                    project_id=row.project_id,
                    environment_id=row.environment_id,
                    details=row.details,
                    sequence_number=row.sequence_number,
                    previous_hash=row.previous_hash,
                    event_hash=row.event_hash,
                    created_at=row.created_at,
                    archived_at=archived_at,
                )
            )
        if rows:
            session.flush()
        return len(rows)

    def list_events(
        self,
        session: Session,
        tenant_id: str | None = None,
        resource_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        stmt = select(AuditLog)
        if tenant_id:
            stmt = stmt.where(AuditLog.organization_id == tenant_id)
        if resource_id:
            stmt = stmt.where(AuditLog.resource_id == resource_id)
        return list(session.scalars(stmt.order_by(AuditLog.created_at.desc()).limit(limit)).all())

    def list_logs(
        self,
        session: Session,
        organization_id: str | None = None,
        project_id: str | None = None,
        environment_id: str | None = None,
        limit: int = 50,
    ) -> list[AuditLog]:
        stmt = select(AuditLog)
        conditions = []
        if organization_id:
            conditions.append(AuditLog.organization_id == organization_id)
        if project_id:
            conditions.append(AuditLog.project_id == project_id)
        if environment_id:
            conditions.append(AuditLog.environment_id == environment_id)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
        return list(session.scalars(stmt).all())
