<<<<<<< HEAD
import ipaddress
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass
class ProviderCapabilities:
    supports_create: bool = True
    supports_read: bool = True
    supports_update: bool = True
    supports_versioning: bool = True
    supports_rotation: bool = True
    supports_deletion: bool = True
    supports_import: bool = True
    supports_metadata: bool = True


@dataclass
class ConnectionTestResult:
    success: bool
    message: str
    status_code: str = "200"
    capabilities: ProviderCapabilities | None = None
    last_validated_at: str | None = None


def validate_provider_endpoint_ssrf(endpoint_url: str | None) -> None:
    """Protects against Server-Side Request Forgery (SSRF) when connecting to external providers."""
    if not endpoint_url:
        return
    parsed = urlparse(endpoint_url)
    if parsed.scheme not in ("https", "http"):
        raise ValueError(f"Invalid URI scheme '{parsed.scheme}'. Only HTTP/HTTPS supported.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid endpoint URL: missing hostname.")

    # Reject localhost, loopback, and private IP addresses.
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        restricted_names = {"localhost", "127.0.0.1", "::1", "metadata.google.internal"}
        if hostname.lower() in restricted_names:
            raise ValueError(f"Endpoint host '{hostname}' is restricted.") from None
    else:
        if ip.is_loopback or ip.is_private or ip.is_reserved or ip.is_multicast:
            raise ValueError(
                f"Endpoint host '{hostname}' resolves to restricted IP range."
            )


class BaseSecretProviderAdapter(ABC):
    """Abstract interface for enterprise secret managers."""

    def __init__(self, provider_config: Any):
        self.config = provider_config

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        pass

    @abstractmethod
    def test_connection(self) -> ConnectionTestResult:
        pass

    @abstractmethod
    def create_secret(
        self, secret_name: str, value: str, metadata: dict[str, Any] | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        """Returns (provider_version_ref, encrypted_value, encryption_metadata)."""
        pass

    @abstractmethod
    def read_secret_value(
        self,
        secret_name: str,
        version_ref: str | None = None,
        encrypted_value: str | None = None,
        encryption_metadata: dict[str, Any] | None = None,
    ) -> str:
        pass

    @abstractmethod
    def update_secret_value(
        self, secret_name: str, value: str, version_ref: str | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        pass

    @abstractmethod
    def rotate_secret(
        self, secret_name: str, current_version_ref: str | None = None
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        pass

    @abstractmethod
    def delete_secret(self, secret_name: str, version_ref: str | None = None) -> bool:
        pass
=======
(full file content here)
>>>>>>> ba111f424d5914bdfb86d71c9c5b059719ee8290
