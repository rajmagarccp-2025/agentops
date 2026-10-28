from __future__ import annotations

from uuid import uuid4

import pytest
from google.api_core.exceptions import NotFound, PreconditionFailed, ServiceUnavailable

import platform_api.api.rag as rag_api
import platform_api.rag_service.service as rag_service
from platform_api.config import Settings
from platform_api.rag_service.document_archive import (
    DocumentArchiveError,
    DocumentArchiveNotFound,
    DocumentArchiveTooLarge,
    GCSDocumentArchive,
)
from platform_api.rag_service.schemas import DocumentCreate, DocumentType
from platform_api.rag_service.service import InMemoryRagRepository
from platform_api.security import Principal


class FakeBlob:
    def __init__(
        self,
        name: str,
        objects: dict[str, tuple[bytes, dict[str, str]]],
        fail_upload: bool = False,
    ) -> None:
        self.name = name
        self.objects = objects
        self.fail_upload = fail_upload
        self.metadata: dict[str, str] | None = None

    def upload_from_string(
        self,
        data: bytes,
        content_type: str,
        checksum: str,
        if_generation_match: int,
    ) -> None:
        del content_type, checksum
        if self.fail_upload:
            raise ServiceUnavailable("Storage unavailable")
        if if_generation_match == 0 and self.name in self.objects:
            raise PreconditionFailed("Object already exists")
        self.objects[self.name] = (data, self.metadata or {})

    def reload(self) -> None:
        if self.name not in self.objects:
            raise NotFound("Object does not exist")
        self.metadata = self.objects[self.name][1]

    def download_as_bytes(self, checksum: str) -> bytes:
        del checksum
        if self.name not in self.objects:
            raise NotFound("Object does not exist")
        return self.objects[self.name][0]

    def delete(self) -> None:
        if self.name not in self.objects:
            raise NotFound("Object does not exist")
        del self.objects[self.name]


class FakeBucket:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, dict[str, str]]] = {}
        self.fail_upload = False

    def blob(self, name: str) -> FakeBlob:
        return FakeBlob(name, self.objects, fail_upload=self.fail_upload)


def test_gcs_archive_round_trip_is_tenant_isolated_and_integrity_checked() -> None:
    bucket = FakeBucket()
    archive = GCSDocumentArchive(bucket, max_bytes=100)
    document_id = str(uuid4())

    archive.store_original("tenant-alpha", document_id, "original document")
    archive.store_original("tenant-beta", document_id, b"other tenant")

    assert len(bucket.objects) == 2
    object_names = list(bucket.objects)
    assert all("tenant-alpha" not in name and "tenant-beta" not in name for name in object_names)
    assert archive.read_original("tenant-alpha", document_id) == b"original document"
    assert archive.read_original("tenant-beta", document_id) == b"other tenant"

    first_name = next(
        name for name, value in bucket.objects.items() if value[0] == b"original document"
    )
    content, metadata = bucket.objects[first_name]
    bucket.objects[first_name] = (content + b" altered", metadata)
    with pytest.raises(DocumentArchiveError, match="integrity verification"):
        archive.read_original("tenant-alpha", document_id)


def test_gcs_archive_checks_byte_limit_and_tenant_metadata() -> None:
    bucket = FakeBucket()
    archive = GCSDocumentArchive(bucket, max_bytes=2)
    document_id = str(uuid4())

    with pytest.raises(DocumentArchiveTooLarge, match="configured archive limit"):
        archive.store_original("tenant", document_id, "€")

    archive = GCSDocumentArchive(bucket, max_bytes=10)
    archive.store_original("tenant", document_id, b"abc")
    object_name = next(iter(bucket.objects))
    content, metadata = bucket.objects[object_name]
    metadata["tenant_hash"] = "different-owner"
    bucket.objects[object_name] = (content, metadata)

    with pytest.raises(DocumentArchiveError, match="metadata"):
        archive.read_original("tenant", document_id)


def test_gcs_archive_surfaces_provider_errors() -> None:
    bucket = FakeBucket()
    bucket.fail_upload = True
    archive = GCSDocumentArchive(bucket, max_bytes=10)

    with pytest.raises(DocumentArchiveError, match="upload failed"):
        archive.store_original("tenant", str(uuid4()), b"data")


def test_gcs_archive_delete_is_idempotent_and_missing_reads_are_explicit() -> None:
    archive = GCSDocumentArchive(FakeBucket(), max_bytes=10)
    document_id = str(uuid4())

    with pytest.raises(DocumentArchiveNotFound):
        archive.read_original("tenant", document_id)
    archive.delete_original("tenant", document_id)


class FakeArchive:
    def __init__(self) -> None:
        self.stored: tuple[str, str, str | bytes] | None = None
        self.deleted: list[tuple[str, str]] = []

    def store_original(self, tenant_id: str, document_id: str, content: str | bytes) -> None:
        self.stored = (tenant_id, document_id, content)

    def read_original(self, tenant_id: str, document_id: str) -> bytes:
        raise NotImplementedError

    def delete_original(self, tenant_id: str, document_id: str) -> None:
        self.deleted.append((tenant_id, document_id))


def test_ingestion_archives_original_and_cleans_up_if_database_save_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = FakeArchive()
    repository = InMemoryRagRepository()
    monkeypatch.setattr(rag_service, "get_document_archive", lambda: archive)
    monkeypatch.setattr(rag_service, "repository", repository)
    payload = DocumentCreate(
        source="source",
        title="Archive test",
        content="original raw bytes",
        document_type=DocumentType.RUNBOOK,
    )

    document = rag_service.ingest_document("tenant", payload)
    assert archive.stored == ("tenant", document.id, payload.content)
    assert repository.get_document("tenant", document.id) == document

    class FailingRepository(InMemoryRagRepository):
        def save_document(self, document, chunks):
            raise RuntimeError("database save failed")

    failing_repository = FailingRepository()
    monkeypatch.setattr(rag_service, "repository", failing_repository)
    with pytest.raises(RuntimeError, match="database save failed"):
        rag_service.ingest_document("tenant", payload)

    assert archive.deleted[-1][0] == "tenant"
    assert archive.deleted[-1][1] != document.id


def test_production_requires_gcs_archive_configuration() -> None:
    production_settings = {
        "app_env": "production",
        "demo_mode": False,
        "database_url": "postgresql://db.example:5432/platform",
        "redis_url": "redis://redis.example:6379/0",
        "oidc_issuer_url": "https://identity.example",
        "oidc_client_id": "platform",
        "jwt_demo_secret": "production-jwt-secret-that-is-long-enough",
        "llm_provider": "vertex",
        "rag_embedding_provider": "vertex",
        "vertex_project_id": "synthetic-project",
    }

    with pytest.raises(ValueError, match="RAG_DOCUMENT_STORAGE_BACKEND"):
        Settings(**production_settings)
    with pytest.raises(ValueError, match="GCS_DOCUMENT_BUCKET"):
        Settings(**production_settings, rag_document_storage_backend="gcs")

    settings = Settings(
        **production_settings,
        rag_document_storage_backend="gcs",
        gcs_document_bucket="owner-provisioned-docs",
    )
    assert settings.gcs_document_bucket == "owner-provisioned-docs"


@pytest.mark.asyncio
async def test_failed_database_commit_restores_deleted_archive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = str(uuid4())

    class DeletionArchive(FakeArchive):
        def __init__(self) -> None:
            super().__init__()
            self.present = True
            self.restored_content: bytes | None = None

        def read_original(self, tenant_id: str, requested_document_id: str) -> bytes:
            assert tenant_id == "tenant"
            assert requested_document_id == document_id
            return b"original archived document"

        def delete_original(self, tenant_id: str, requested_document_id: str) -> None:
            super().delete_original(tenant_id, requested_document_id)
            self.present = False

        def store_original(
            self, tenant_id: str, requested_document_id: str, content: str | bytes
        ) -> None:
            super().store_original(tenant_id, requested_document_id, content)
            self.present = True
            self.restored_content = bytes(content)

    class FailingCommitDB:
        rollback_called = False

        def commit(self) -> None:
            raise RuntimeError("database commit failed")

        def rollback(self) -> None:
            self.rollback_called = True

    archive = DeletionArchive()
    db = FailingCommitDB()
    document = type("Document", (), {"title": "Runbook", "scope": "project"})()
    environment = type(
        "Environment",
        (),
        {"project_id": "project", "id": "environment", "type": "Development"},
    )()

    monkeypatch.setattr(
        rag_api,
        "repository",
        type("Repository", (), {"get_document": lambda *_: document})(),
    )
    monkeypatch.setattr(rag_api, "get_document_archive", lambda: archive)
    monkeypatch.setattr(
        rag_api, "require_active_environment", lambda *_args, **_kwargs: environment
    )
    monkeypatch.setattr(rag_api, "delete_document", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        rag_api,
        "AuditLogRepository",
        lambda: type("AuditRepository", (), {"record_event": lambda *_args, **_kwargs: None})(),
    )
    principal = Principal(
        subject="user",
        tenant_id="tenant",
        roles=frozenset(),
        permissions=frozenset(),
        project_id="project",
        environment_id="environment",
    )

    with pytest.raises(RuntimeError, match="database commit failed"):
        await rag_api.remove_document(document_id, principal, db)

    assert db.rollback_called
    assert archive.restored_content == b"original archived document"
    assert archive.present
