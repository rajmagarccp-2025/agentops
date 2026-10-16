import base64
import os
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from platform_api.config import get_settings


def _derive_master_key() -> bytes:
    """Derives a 256-bit AES key from configured application master key or JWT secret."""
    settings = get_settings()
    master_secret = (
        getattr(settings, "secret_storage_master_key", None)
        or settings.jwt_demo_secret.get_secret_value()
    )

    # Use fixed salt for master key derivation across process restarts
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"agentops-platform-secrets-master-salt-v1",
        iterations=100_000,
    )
    return kdf.derive(master_secret.encode("utf-8"))


class InternalCryptoService:
    """Production-grade AES-256-GCM authenticated encryption service for internal secret store."""

    @staticmethod
    def encrypt(plaintext: str) -> tuple[str, dict[str, Any]]:
        """Encrypts plaintext using AES-256-GCM. Returns (base64_ciphertext, encryption_metadata)."""
        key = _derive_master_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        ciphertext_bytes = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

        b64_ciphertext = base64.b64encode(ciphertext_bytes).decode("utf-8")
        metadata = {
            "algorithm": "AES-256-GCM",
            "nonce_b64": base64.b64encode(nonce).decode("utf-8"),
            "key_version": 1,
            "kdf": "PBKDF2-HMAC-SHA256",
        }
        return b64_ciphertext, metadata

    @staticmethod
    def decrypt(b64_ciphertext: str, metadata: dict[str, Any]) -> str:
        """Decrypts base64 ciphertext using AES-256-GCM and stored metadata."""
        key = _derive_master_key()
        aesgcm = AESGCM(key)
        nonce = base64.b64decode(metadata["nonce_b64"])
        ciphertext_bytes = base64.b64decode(b64_ciphertext)

        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_bytes, None)
        return plaintext_bytes.decode("utf-8")
