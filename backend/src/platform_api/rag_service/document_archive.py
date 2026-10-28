from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Protocol
from uuid import UUID

from google.api_core.exceptions import GoogleAPIError, NotFound, PreconditionFailed
from google.auth.exceptions import GoogleAuthError
from google.cloud.storage import Bucket, Client  # type: ignore[import-untyped]

from platform_api.config import get_settings


class DocumentArchiveError(RuntimeError):
    pass


class DocumentArchiveNotFound(DocumentArchiveError):
    pass


class DocumentArchiveTooLarge(DocumentArchiveError):
    pass


class DocumentArchive(Protocol):
    def store_original(self, tenant_id: str, document_id: str, content: str | bytes) -> None: ...

    def read_original(self, tenant_id: str, document_id: str) -> bytes: ...

    def delete_original(self, tenant_id: str, document_id: str) -> None: ...


class GCSDocumentArchive:
    def __init__(self, bucket: Bucket, max_bytes: int) -> None:
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        self._bucket = bucket
        self._max_bytes = max_bytes

    @staticmethod
    def _object_name(tenant_id: str, document_id: str) -> str:
        tenant_hash = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()
        try:
            normalized_document_id = str(UUID(document_id))
        except ValueError as exc:
            raise ValueError("document_id must be a UUID") from exc
        return f"tenants/{tenant_hash}/documents/{normalized_document_id}/original"

    def store_original(self, tenant_id: str, document_id: str, content: str | bytes) -> None:
        payload = content.encode("utf-8") if isinstance(content, str) else content
        if len(payload) > self._max_bytes:
            raise DocumentArchiveTooLarge(
                f"Document exceeds configured archive limit of {self._max_bytes} bytes"
            )

        object_name = self._object_name(tenant_id, document_id)
        checksum = hashlib.sha256(payload).hexdigest()
        blob = self._bucket.blob(object_name)
        blob.metadata = {
            "document_id": str(UUID(document_id)),
            "tenant_hash": hashlib.sha256(tenant_id.encode("utf-8")).hexdigest(),
            "sha256": checksum,
            "size_bytes": str(len(payload)),
            "schema_version": "1",
        }
        try:
            blob.upload_from_string(
                payload,
                content_type="application/octet-stream",
                checksum="auto",
                if_generation_match=0,
            )
        except PreconditionFailed:
            existing = self.read_original(tenant_id, document_id)
            if existing != payload:
                raise DocumentArchiveError(
                    "An archive object already exists with different content"
                ) from None
        except GoogleAPIError as exc:
            raise DocumentArchiveError("GCS document archive upload failed") from exc

    def read_original(self, tenant_id: str, document_id: str) -> bytes:
        object_name = self._object_name(tenant_id, document_id)
        blob = self._bucket.blob(object_name)
        try:
            blob.reload()
        except NotFound as exc:
            raise DocumentArchiveNotFound("Archived document was not found") from exc
        except GoogleAPIError as exc:
            raise DocumentArchiveError("GCS document archive metadata read failed") from exc

        metadata = blob.metadata or {}
        expected_tenant_hash = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()
        if (
            metadata.get("document_id") != str(UUID(document_id))
            or metadata.get("tenant_hash") != expected_tenant_hash
            or metadata.get("schema_version") != "1"
        ):
            raise DocumentArchiveError("Archived document metadata does not match its owner")

        try:
            payload = bytes(blob.download_as_bytes(checksum="auto"))
        except NotFound as exc:
            raise DocumentArchiveNotFound("Archived document was not found") from exc
        except GoogleAPIError as exc:
            raise DocumentArchiveError("GCS document archive download failed") from exc
        checksum = hashlib.sha256(payload).hexdigest()
        if metadata.get("sha256") != checksum or metadata.get("size_bytes") != str(len(payload)):
            raise DocumentArchiveError("Archived document integrity verification failed")
        if len(payload) > self._max_bytes:
            raise DocumentArchiveError("Archived document exceeds the configured size limit")
        return payload

    def delete_original(self, tenant_id: str, document_id: str) -> None:
        blob = self._bucket.blob(self._object_name(tenant_id, document_id))
        try:
            blob.delete()
        except NotFound:
            return
        except GoogleAPIError as exc:
            raise DocumentArchiveError("GCS document archive deletion failed") from exc


@lru_cache(maxsize=1)
def get_document_archive() -> DocumentArchive | None:
    settings = get_settings()
    if settings.rag_document_storage_backend == "postgres":
        return None
    if settings.rag_document_storage_backend != "gcs":
        raise ValueError(
            f"Unsupported RAG document storage backend: {settings.rag_document_storage_backend}"
        )
    if not settings.gcs_document_bucket:
        raise ValueError("GCS_DOCUMENT_BUCKET must be configured for GCS document archiving")

    try:
        client = Client()
    except GoogleAuthError as exc:
        raise DocumentArchiveError("GCS Application Default Credentials are unavailable") from exc
    return GCSDocumentArchive(
        bucket=client.bucket(settings.gcs_document_bucket),
        max_bytes=settings.rag_document_max_bytes,
    )
