from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SecretProviderCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    provider_type: str = Field(..., min_length=2, max_length=50)
    # internal_encrypted, aws_secrets_manager, azure_key_vault,
    # gcp_secret_manager, hashicorp_vault
    endpoint_url: str | None = None
    vault_identifier: str | None = None
    region: str | None = None
    auth_method: str = "workload_identity"
    credentials_config: dict[str, Any] | None = None
    required_roles: list[str] = Field(default_factory=list)


class SecretProviderResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    provider_type: str
    endpoint_url: str | None = None
    vault_identifier: str | None = None
    region: str | None = None
    auth_method: str
    required_roles: list[str]
    status: str
    last_validated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SecretAssignmentCreate(BaseModel):
    entity_type: str = Field(
        ..., min_length=2, max_length=50
    )  # agent, application, service, model_deployment, workflow, pipeline, runtime_environment
    entity_id: str = Field(..., min_length=1, max_length=255)
    entity_name: str = Field(..., min_length=1, max_length=200)


class SecretAssignmentResponse(BaseModel):
    id: str
    secret_id: str
    entity_type: str
    entity_id: str
    entity_name: str
    assigned_by: str
    assigned_at: datetime


class SecretCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: str = Field(default="", max_length=500)
    secret_type: str = Field(default="api_key")
    # api_key, database_credential, cloud_credential, password, oauth_secret,
    # certificate, ssh_key, custom
    provider_id: str = Field(..., min_length=1)
    scope: str = Field(default="environment")  # organization, project, environment
    project_id: str | None = None
    environment_id: str | None = None
    value: str = Field(..., min_length=1)
    expiration_date: datetime | None = None
    rotation_interval_days: int | None = Field(default=None, ge=1, le=365)
    assignments: list[SecretAssignmentCreate] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SecretUpdate(BaseModel):
    description: str | None = None
    value: str | None = None
    expiration_date: datetime | None = None
    rotation_interval_days: int | None = Field(default=None, ge=1, le=365)
    status: Literal["active", "disabled", "pending_deletion"] | None = None
    metadata: dict[str, Any] | None = None


class SecretVersionResponse(BaseModel):
    id: str
    secret_id: str
    version_num: int
    provider_version_ref: str | None = None
    created_by: str
    created_at: datetime
    comment: str


class SecretMetadataResponse(BaseModel):
    id: str
    name: str
    description: str
    secret_type: str
    provider_id: str
    provider_type: str
    provider_name: str
    scope: str
    tenant_id: str
    project_id: str | None = None
    environment_id: str | None = None
    current_version_num: int
    created_by: str
    modified_by: str
    created_at: datetime
    updated_at: datetime
    status: str
    expiration_date: datetime | None = None
    rotation_interval_days: int | None = None
    last_rotated_at: datetime | None = None
    metadata: dict[str, Any]
    assigned_entities: list[SecretAssignmentResponse] = Field(default_factory=list)
    # Note: Raw secret value is explicitly write-only and excluded from standard responses!


class SecretValueRevealResponse(BaseModel):
    secret_id: str
    secret_name: str
    version_num: int
    value: str
    revealed_at: datetime
    revealed_by: str


class SecretResolveRequest(BaseModel):
    secret_identifier: str = Field(..., description="Secret Name or Secret UUID")
    environment_id: str | None = None
    project_id: str | None = None
    requesting_entity_type: str = Field(default="service")
    requesting_entity_id: str = Field(default="runtime")


class SecretResolveResponse(BaseModel):
    secret_id: str
    secret_name: str
    version_num: int
    value: str
    environment_id: str | None = None
    provider_type: str
