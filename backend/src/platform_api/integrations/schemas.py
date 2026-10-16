import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from platform_api.contracts.domain import CloudProvider


class CloudIntegrationCreate(BaseModel):
    provider: CloudProvider
    display_name: str = Field(min_length=2, max_length=150)
    account_id: str = Field(min_length=1, max_length=200)
    identity_reference: str = Field(min_length=1, max_length=500)

    @field_validator("account_id")
    @classmethod
    def reject_account_credentials(cls, value: str) -> str:
        candidate = value.strip()
        if _looks_like_credential(candidate):
            raise ValueError("Enter an account identifier, not a credential.")
        return candidate

    @field_validator("identity_reference")
    @classmethod
    def reject_credential_material(cls, value: str) -> str:
        candidate = value.strip()
        if _looks_like_credential(candidate):
            raise ValueError("Enter an identity or secret-manager reference, not a credential.")
        return candidate

    @model_validator(mode="after")
    def validate_identity_reference(self) -> "CloudIntegrationCreate":
        value = self.identity_reference
        accepted = {
            CloudProvider.AWS: value.startswith("arn:aws:iam::") or value.startswith("secret://"),
            CloudProvider.AZURE: value.startswith("/subscriptions/")
            or value.startswith(("identity://", "secret://")),
            CloudProvider.GCP: value.endswith(".iam.gserviceaccount.com")
            or value.startswith(("identity://", "secret://")),
            CloudProvider.KUBERNETES: value.startswith(("cluster://", "identity://", "secret://")),
            CloudProvider.OPENSHIFT: value.startswith(("cluster://", "identity://", "secret://")),
            CloudProvider.GITHUB: value.startswith(("oidc://", "identity://", "secret://")),
            CloudProvider.ON_PREM: value.startswith(("identity://", "secret://")),
        }
        if not accepted[self.provider]:
            raise ValueError(
                "Use a provider-appropriate identity identifier or secret-manager reference."
            )
        return self


class CloudIntegrationRecord(BaseModel):
    id: str
    provider: CloudProvider
    display_name: str
    account_id: str
    identity_reference: str
    status: str
    status_detail: str
    created_at: datetime


class CloudProviderCapability(BaseModel):
    provider: CloudProvider
    connection_mode: str
    verification_supported: bool


class CloudIntegrationCatalog(BaseModel):
    providers: list[CloudProviderCapability]
    connections: list[CloudIntegrationRecord]


def _looks_like_credential(value: str) -> bool:
    return (
        value.lower().startswith(("bearer ", "ghp_", "gho_", "github_pat_"))
        or value.startswith("AKIA")
        or bool(re.fullmatch(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", value))
    )
