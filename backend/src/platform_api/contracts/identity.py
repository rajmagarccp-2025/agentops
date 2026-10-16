"""Authentication principal and tenant context contracts."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from platform_api.contracts.domain import CloudProvider, Environment


class Principal(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject: str = Field(min_length=1, max_length=255)
    tenant_id: str = Field(min_length=1, max_length=100)
    roles: frozenset[str] = Field(default_factory=frozenset)
    permissions: frozenset[str] = Field(default_factory=frozenset)
    auth_context: dict[str, Any] = Field(default_factory=dict)
    issuer: str = Field(default="platform-auth", max_length=255)
    audience: str = Field(default="platform-api", max_length=255)


class TenantContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str = Field(min_length=1, max_length=100)
    project_id: str | None = Field(default=None, max_length=100)
    environment: Environment = Environment.PRODUCTION
    cloud_account_bindings: dict[CloudProvider, str] = Field(default_factory=dict)
