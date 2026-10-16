"""Production Provider Adapter Foundation & Registry.

Architectural Guarantees:
1. Agents NEVER import provider SDKs. All infrastructure interactions route through Provider Adapters via MCP.
2. Only Provider Adapters communicate with provider APIs.
3. Credential resolution happens outside agents (Workload Identity / Managed Identity / STS / ServiceAccount).
4. Strict capability-specific permission profiles. No AdministratorAccess universal credentials.
5. Extensible architecture allowing easy addition of custom cloud/platform providers.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from platform_api.contracts.domain import CloudProvider
from platform_api.security import Principal


class ProviderCredentialContext(BaseModel):
    """Encapsulates workload identity & authorization context resolved outside agents."""

    provider: CloudProvider
    tenant_id: str
    account_id: str | None = None
    role_arn_or_identity: str | None = None
    cluster_context: str | None = None
    permission_profile: str = Field(
        default="read-only",
        description="Capability-specific profile e.g. 'read-only', 'remediation-scaler'",
    )
    credentials_valid: bool = True
    token_expiry: str | None = None


class BaseProviderAdapter(ABC):
    """Abstract base class for all production provider adapters."""

    def __init__(self, provider: CloudProvider, permission_profile: str = "read-only") -> None:
        self.provider = provider
        self.permission_profile = permission_profile

    @abstractmethod
    def resolve_credentials(
        self, principal: Principal, account_id: str | None = None
    ) -> ProviderCredentialContext:
        """Resolve workload identity/STS/Managed Identity outside the agent boundary."""
        pass

    @abstractmethod
    def execute_read(
        self,
        resource_type: str,
        action: str,
        parameters: dict[str, Any],
        ctx: ProviderCredentialContext,
    ) -> dict[str, Any]:
        """Execute READ operations against provider API."""
        pass

    @abstractmethod
    def execute_allowlisted_mutation(
        self,
        resource_type: str,
        action: str,
        parameters: dict[str, Any],
        ctx: ProviderCredentialContext,
    ) -> dict[str, Any]:
        """Execute explicitly allowlisted mutation operations against provider API."""
        pass


class ProviderAdapterRegistry:
    """Registry managing provider adapters for AWS, GCP, Azure, Kubernetes, OpenShift, GitHub, and custom providers."""

    def __init__(self) -> None:
        self._adapters: dict[CloudProvider, BaseProviderAdapter] = {}

    def register(self, provider: CloudProvider, adapter: BaseProviderAdapter) -> None:
        self._adapters[provider] = adapter

    def get(self, provider: CloudProvider) -> BaseProviderAdapter:
        if provider not in self._adapters:
            raise KeyError(f"No provider adapter registered for '{provider.value}'")
        return self._adapters[provider]


# Global adapter registry
provider_registry = ProviderAdapterRegistry()
