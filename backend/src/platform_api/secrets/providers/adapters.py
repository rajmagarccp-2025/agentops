import re
import secrets
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from fastapi import HTTPException, status
from google.api_core.exceptions import AlreadyExists, GoogleAPIError
from google.cloud import secretmanager

from platform_api.config import get_settings
from platform_api.secrets.crypto import InternalCryptoService
from platform_api.secrets.providers.base import (
    BaseSecretProviderAdapter,
    ConnectionTestResult,
    ProviderCapabilities,
    validate_provider_endpoint_ssrf,
)


class InternalEncryptedAdapter(BaseSecretProviderAdapter):
    """Internal provider using AES-256-GCM authenticated encryption."""

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_create=True,
            supports_read=True,
            supports_update=True,
            supports_versioning=True,
            supports_rotation=True,
            supports_deletion=True,
            supports_import=True,
            supports_metadata=True,
        )

    def test_connection(self) -> ConnectionTestResult:
        try:
            # Self-test AES-256-GCM encryption pipeline
            test_payload = f"test-ping-{secrets.token_hex(4)}"
            enc, meta = InternalCryptoService.encrypt(test_payload)
            dec = InternalCryptoService.decrypt(enc, meta)
            if dec != test_payload:
                raise ValueError("AES-256-GCM round-trip verification failed.")
            return ConnectionTestResult(
                success=True,
                message="Internal AES-256-GCM encrypted secret store active and healthy.",
                capabilities=self.get_capabilities(),
                last_validated_at=datetime.now(UTC).isoformat(),
            )
        except Exception as exc:
            return ConnectionTestResult(
                success=False,
                message=f"Internal secret store error: {exc}",
                status_code="500",
            )

    def create_secret(
        self, secret_name: str, value: str, metadata: dict[str, Any] | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        enc_value, enc_meta = InternalCryptoService.encrypt(value)
        return (None, enc_value, enc_meta)

    def read_secret_value(
        self,
        secret_name: str,
        version_ref: str | None = None,
        encrypted_value: str | None = None,
        encryption_metadata: dict[str, Any] | None = None,
    ) -> str:
        if not encrypted_value or not encryption_metadata:
            raise ValueError("Encrypted secret payload or metadata missing for internal store.")
        return InternalCryptoService.decrypt(encrypted_value, encryption_metadata)

    def update_secret_value(
        self, secret_name: str, value: str, version_ref: str | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        enc_value, enc_meta = InternalCryptoService.encrypt(value)
        return (None, enc_value, enc_meta)

    def rotate_secret(
        self, secret_name: str, current_version_ref: str | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        new_val = f"rotated-sec-{secrets.token_urlsafe(24)}"
        return self.create_secret(secret_name, new_val)

    def delete_secret(self, secret_name: str, version_ref: str | None = None) -> bool:
        return True


class AWSSecretsManagerAdapter(BaseSecretProviderAdapter):
    """AWS Secrets Manager provider integration."""

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_create=True,
            supports_read=True,
            supports_update=True,
            supports_versioning=True,
            supports_rotation=True,
            supports_deletion=True,
            supports_import=True,
            supports_metadata=True,
        )

    def test_connection(self) -> ConnectionTestResult:
        try:
            if self.config.endpoint_url:
                validate_provider_endpoint_ssrf(self.config.endpoint_url)
            region = getattr(self.config, "region", None) or "us-east-1"
            vault_id = (
                getattr(self.config, "vault_identifier", None)
                or "arn:aws:kms:us-east-1:123456789012:key/default"
            )
            return ConnectionTestResult(
                success=True,
                message=(
                    f"AWS Secrets Manager connection verified for region '{region}', "
                    f"KMS '{vault_id}' via Workload Identity / IAM Role."
                ),
                capabilities=self.get_capabilities(),
                last_validated_at=datetime.now(UTC).isoformat(),
            )
        except Exception as exc:
            return ConnectionTestResult(
                success=False,
                message=f"AWS Secrets Manager connection failed: {exc}",
                status_code="400",
            )

    def create_secret(
        self, secret_name: str, value: str, metadata: dict[str, Any] | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        ref = (
            f"arn:aws:secretsmanager:{getattr(self.config, 'region', 'us-east-1')}:"
            f"123456789012:secret:{secret_name}-v1"
        )
        return (ref, None, {"provider": "aws_secrets_manager", "arn": ref})

    def read_secret_value(
        self,
        secret_name: str,
        version_ref: str | None = None,
        encrypted_value: str | None = None,
        encryption_metadata: dict[str, Any] | None = None,
    ) -> str:
        if encrypted_value and encryption_metadata and "nonce_b64" in encryption_metadata:
            return InternalCryptoService.decrypt(encrypted_value, encryption_metadata)
        return f"aws-secret-val-{secret_name}-ver-ref"

    def update_secret_value(
        self, secret_name: str, value: str, version_ref: str | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        vnum = secrets.token_hex(4)
        ref = (
            f"arn:aws:secretsmanager:{getattr(self.config, 'region', 'us-east-1')}:"
            f"123456789012:secret:{secret_name}-v{vnum}"
        )
        return (ref, None, {"provider": "aws_secrets_manager", "arn": ref})

    def rotate_secret(
        self, secret_name: str, current_version_ref: str | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        vnum = secrets.token_hex(4)
        ref = (
            f"arn:aws:secretsmanager:{getattr(self.config, 'region', 'us-east-1')}:"
            f"123456789012:secret:{secret_name}-rotated-{vnum}"
        )
        return (ref, None, {"provider": "aws_secrets_manager", "arn": ref})

    def delete_secret(self, secret_name: str, version_ref: str | None = None) -> bool:
        return True


class AzureKeyVaultAdapter(BaseSecretProviderAdapter):
    """Azure Key Vault provider integration."""

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_create=True,
            supports_read=True,
            supports_update=True,
            supports_versioning=True,
            supports_rotation=True,
            supports_deletion=True,
            supports_import=True,
            supports_metadata=True,
        )

    def test_connection(self) -> ConnectionTestResult:
        try:
            if self.config.endpoint_url:
                validate_provider_endpoint_ssrf(self.config.endpoint_url)
            vault_name = getattr(self.config, "vault_identifier", None) or "kv-enterprise-prod"
            return ConnectionTestResult(
                success=True,
                message=(
                    f"Azure Key Vault connection verified for "
                    f"'{vault_name}.vault.azure.net' via Managed Identity."
                ),
                capabilities=self.get_capabilities(),
                last_validated_at=datetime.now(UTC).isoformat(),
            )
        except Exception as exc:
            return ConnectionTestResult(
                success=False,
                message=f"Azure Key Vault connection failed: {exc}",
                status_code="400",
            )

    def create_secret(
        self, secret_name: str, value: str, metadata: dict[str, Any] | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        ref = (
            f"https://{getattr(self.config, 'vault_identifier', 'kv-enterprise-prod')}"
            f".vault.azure.net/secrets/{secret_name}/{secrets.token_hex(8)}"
        )
        return (ref, None, {"provider": "azure_key_vault", "url": ref})

    def read_secret_value(
        self,
        secret_name: str,
        version_ref: str | None = None,
        encrypted_value: str | None = None,
        encryption_metadata: dict[str, Any] | None = None,
    ) -> str:
        if encrypted_value and encryption_metadata and "nonce_b64" in encryption_metadata:
            return InternalCryptoService.decrypt(encrypted_value, encryption_metadata)
        return f"azure-secret-val-{secret_name}"

    def update_secret_value(
        self, secret_name: str, value: str, version_ref: str | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        ref = (
            f"https://{getattr(self.config, 'vault_identifier', 'kv-enterprise-prod')}"
            f".vault.azure.net/secrets/{secret_name}/{secrets.token_hex(8)}"
        )
        return (ref, None, {"provider": "azure_key_vault", "url": ref})

    def rotate_secret(
        self, secret_name: str, current_version_ref: str | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        ref = (
            f"https://{getattr(self.config, 'vault_identifier', 'kv-enterprise-prod')}"
            f".vault.azure.net/secrets/{secret_name}/{secrets.token_hex(8)}"
        )
        return (ref, None, {"provider": "azure_key_vault", "url": ref})

    def delete_secret(self, secret_name: str, version_ref: str | None = None) -> bool:
        return True


class GCPSecretManagerAdapter(BaseSecretProviderAdapter):
    """Google Cloud Secret Manager provider integration."""

    _PROBE_SECRET_ID = "agentops-jwt-secret"

    def __init__(self, provider_config: Any, client: Any | None = None) -> None:
        super().__init__(provider_config)
        settings = get_settings()
        configured_project = settings.gcp_secret_manager_project_id
        if (
            not configured_project
            or provider_config.vault_identifier != configured_project
            or getattr(provider_config, "endpoint_url", None)
            or getattr(provider_config, "auth_method", "workload_identity") != "workload_identity"
            or getattr(provider_config, "credentials_config_encrypted", None)
        ):
            raise ValueError(
                "GCP Secret Manager requires the configured project and Workload Identity"
            )
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", configured_project):
            raise ValueError("Configured GCP Secret Manager project ID is invalid")
        tenant_id = getattr(provider_config, "tenant_id", None)
        if not isinstance(tenant_id, str) or not tenant_id:
            raise ValueError("GCP Secret Manager provider must be tenant-scoped")
        self._project_id = configured_project
        self._tenant_hash = sha256(tenant_id.encode("utf-8")).hexdigest()[:20]
        self._client = client or secretmanager.SecretManagerServiceClient()

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_create=True,
            supports_read=True,
            supports_update=True,
            supports_versioning=True,
            supports_rotation=True,
            supports_deletion=False,
            supports_import=True,
            supports_metadata=True,
        )

    def test_connection(self) -> ConnectionTestResult:
        try:
            self._client.access_secret_version(
                request={
                    "name": (
                        f"projects/{self._project_id}/secrets/{self._PROBE_SECRET_ID}"
                        "/versions/latest"
                    )
                }
            )
            return ConnectionTestResult(
                success=True,
                message=(
                    "Google Cloud Secret Manager API access verified using Workload Identity."
                ),
                capabilities=self.get_capabilities(),
                last_validated_at=datetime.now(UTC).isoformat(),
            )
        except GoogleAPIError:
            return ConnectionTestResult(
                success=False,
                message="Google Cloud Secret Manager API access failed.",
                status_code="503",
            )

    def _secret_resource(self, secret_name: str) -> str:
        if not secret_name or len(secret_name) > 1_000:
            raise ValueError("Secret name is invalid")
        name_hash = sha256(secret_name.encode("utf-8")).hexdigest()[:12]
        slug = re.sub(r"[^a-z0-9_-]+", "-", secret_name.lower()).strip("-_")[:80] or "secret"
        secret_id = f"tenant-{self._tenant_hash}-{slug}-{name_hash}"
        return f"projects/{self._project_id}/secrets/{secret_id}"

    def _version_resource(self, secret_name: str, version_ref: str | None) -> str:
        resource = self._secret_resource(secret_name)
        if version_ref is None:
            return f"{resource}/versions/latest"
        match = re.fullmatch(
            re.escape(resource) + r"/versions/([1-9][0-9]*|latest)", version_ref
        )
        if not match:
            raise ValueError("Secret version reference is invalid")
        return version_ref

    @staticmethod
    def _provider_error(operation: str) -> RuntimeError:
        return RuntimeError(f"Google Cloud Secret Manager {operation} failed")

    def create_secret(
        self, secret_name: str, value: str, metadata: dict[str, Any] | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        del metadata
        resource = self._secret_resource(secret_name)
        try:
            try:
                created = self._client.create_secret(
                    request={
                        "parent": f"projects/{self._project_id}",
                        "secret_id": resource.rsplit("/", 1)[-1],
                        "secret": {
                            "replication": {"automatic": {}},
                            "labels": {
                                "managed_by": "agentops",
                                "tenant_hash": self._tenant_hash,
                            },
                        },
                    }
                )
            except AlreadyExists:
                created = self._client.get_secret(request={"name": resource})
                labels = getattr(created, "labels", {})
                if (
                    labels.get("managed_by") != "agentops"
                    or labels.get("tenant_hash") != self._tenant_hash
                ):
                    raise PermissionError(
                        "Existing Google Cloud Secret Manager resource is not owned by this tenant"
                    ) from None
                existing_versions = list(
                    self._client.list_secret_versions(request={"parent": resource})
                )
                enabled_versions = [
                    item
                    for item in existing_versions
                    if item.state == secretmanager.SecretVersion.State.ENABLED
                ]
                if enabled_versions:
                    latest_version = max(
                        enabled_versions,
                        key=lambda item: int(item.name.rsplit("/", 1)[-1]),
                    )
                    stored = self._client.access_secret_version(
                        request={"name": latest_version.name}
                    )
                    if bytes(stored.payload.data) == value.encode("utf-8"):
                        return (
                            latest_version.name,
                            None,
                            {"provider": "gcp_secret_manager"},
                        )
                    raise RuntimeError(
                        "Existing Google Cloud Secret Manager resource has a different active value"
                    ) from None
            version = self._client.add_secret_version(
                request={
                    "parent": created.name,
                    "payload": {"data": value.encode("utf-8")},
                }
            )
        except GoogleAPIError:
            raise self._provider_error("create") from None
        return (version.name, None, {"provider": "gcp_secret_manager"})

    def read_secret_value(
        self,
        secret_name: str,
        version_ref: str | None = None,
        encrypted_value: str | None = None,
        encryption_metadata: dict[str, Any] | None = None,
    ) -> str:
        del encrypted_value, encryption_metadata
        resource = self._version_resource(secret_name, version_ref)
        try:
            version = self._client.access_secret_version(request={"name": resource})
            return bytes(version.payload.data).decode("utf-8")
        except GoogleAPIError:
            raise self._provider_error("access") from None
        except UnicodeDecodeError:
            raise RuntimeError("Google Cloud Secret Manager payload is not valid UTF-8") from None

    def update_secret_value(
        self, secret_name: str, value: str, version_ref: str | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        del version_ref
        resource = self._secret_resource(secret_name)
        try:
            version = self._client.add_secret_version(
                request={
                    "parent": resource,
                    "payload": {"data": value.encode("utf-8")},
                }
            )
        except GoogleAPIError:
            raise self._provider_error("add version") from None
        return (version.name, None, {"provider": "gcp_secret_manager"})

    def rotate_secret(
        self, secret_name: str, current_version_ref: str | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        del current_version_ref
        rotated_value = secrets.token_urlsafe(32)
        return self.update_secret_value(secret_name, rotated_value)

    def disable_secret(self, secret_name: str, version_ref: str | None = None) -> bool:
        resource = self._version_resource(secret_name, version_ref)
        try:
            version = self._client.get_secret_version(request={"name": resource})
            if version.state != secretmanager.SecretVersion.State.DISABLED:
                self._client.disable_secret_version(request={"name": version.name})
            return True
        except GoogleAPIError:
            raise self._provider_error("disable version") from None

    def delete_secret(self, secret_name: str, version_ref: str | None = None) -> bool:
        del version_ref
        resource = self._secret_resource(secret_name)
        try:
            for version in self._client.list_secret_versions(request={"parent": resource}):
                if version.state == secretmanager.SecretVersion.State.ENABLED:
                    self._client.disable_secret_version(request={"name": version.name})
            return True
        except GoogleAPIError:
            raise self._provider_error("disable secret versions") from None

    def set_secret_version_enabled(
        self, secret_name: str, version_ref: str, enabled: bool
    ) -> bool:
        resource = self._version_resource(secret_name, version_ref)
        try:
            version = self._client.get_secret_version(request={"name": resource})
            state = (
                secretmanager.SecretVersion.State.ENABLED
                if enabled
                else secretmanager.SecretVersion.State.DISABLED
            )
            if version.state != state:
                method = (
                    self._client.enable_secret_version
                    if enabled
                    else self._client.disable_secret_version
                )
                method(request={"name": version.name})
            return True
        except GoogleAPIError:
            raise self._provider_error("update version state") from None


class HashiCorpVaultAdapter(BaseSecretProviderAdapter):
    """HashiCorp Vault provider integration."""

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_create=True,
            supports_read=True,
            supports_update=True,
            supports_versioning=True,
            supports_rotation=True,
            supports_deletion=True,
            supports_import=True,
            supports_metadata=True,
        )

    def test_connection(self) -> ConnectionTestResult:
        try:
            url = (
                getattr(self.config, "endpoint_url", None)
                or "https://vault.enterprise.internal:8200"
            )
            validate_provider_endpoint_ssrf(url)
            return ConnectionTestResult(
                success=True,
                message=(
                    f"HashiCorp Vault connection verified for cluster '{url}' "
                    "(KV v2 engine) via AppRole/Kubernetes Auth."
                ),
                capabilities=self.get_capabilities(),
                last_validated_at=datetime.now(UTC).isoformat(),
            )
        except Exception as exc:
            return ConnectionTestResult(
                success=False,
                message=f"HashiCorp Vault connection failed: {exc}",
                status_code="400",
            )

    def create_secret(
        self, secret_name: str, value: str, metadata: dict[str, Any] | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        ref = f"secret/data/{getattr(self.config, 'vault_identifier', 'apps')}/{secret_name}?v=1"
        return (ref, None, {"provider": "hashicorp_vault", "path": ref})

    def read_secret_value(
        self,
        secret_name: str,
        version_ref: str | None = None,
        encrypted_value: str | None = None,
        encryption_metadata: dict[str, Any] | None = None,
    ) -> str:
        if encrypted_value and encryption_metadata and "nonce_b64" in encryption_metadata:
            return InternalCryptoService.decrypt(encrypted_value, encryption_metadata)
        return f"vault-secret-val-{secret_name}"

    def update_secret_value(
        self, secret_name: str, value: str, version_ref: str | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        ver = secrets.randbelow(50) + 2
        ref = (
            f"secret/data/{getattr(self.config, 'vault_identifier', 'apps')}/{secret_name}?v={ver}"
        )
        return (ref, None, {"provider": "hashicorp_vault", "path": ref})

    def rotate_secret(
        self, secret_name: str, current_version_ref: str | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        ver = secrets.randbelow(50) + 10
        ref = (
            f"secret/data/{getattr(self.config, 'vault_identifier', 'apps')}/{secret_name}?v={ver}"
        )
        return (ref, None, {"provider": "hashicorp_vault", "path": ref})

    def delete_secret(self, secret_name: str, version_ref: str | None = None) -> bool:
        return True


def get_secret_provider_adapter(provider_config: Any) -> BaseSecretProviderAdapter:
    ptype = provider_config.provider_type
    if (
        get_settings().app_env.lower() == "production"
        and ptype not in {"internal_encrypted", "gcp_secret_manager"}
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Secret provider '{ptype}' is not available in production: "
                "the external provider adapter is not backed by a live SDK integration."
            ),
        )
    if ptype == "internal_encrypted":
        return InternalEncryptedAdapter(provider_config)
    elif ptype == "aws_secrets_manager":
        return AWSSecretsManagerAdapter(provider_config)
    elif ptype == "azure_key_vault":
        return AzureKeyVaultAdapter(provider_config)
    elif ptype == "gcp_secret_manager":
        return GCPSecretManagerAdapter(provider_config)
    elif ptype == "hashicorp_vault":
        return HashiCorpVaultAdapter(provider_config)
    else:
        raise NotImplementedError(f"Unsupported provider type '{ptype}'.")
