import os
from uuid import uuid4

import pytest

from platform_api.config import get_settings
from platform_api.database import engine
from platform_api.llm.providers import VertexAIProvider
from platform_api.llm.types import ChatMessage, LLMRequest, MessageRole
from platform_api.rag_service.embedding import get_embedding_provider
from platform_api.rag_service.repository import SqlAlchemyRagRepository
from platform_api.rag_service.schemas import (
    DocumentChunk,
    DocumentRecord,
    DocumentType,
    utc_now,
)
from platform_api.rag_service.service import repository, retrieve

pytestmark = pytest.mark.integration


def _require_gcp_integration() -> None:
    if os.getenv("RUN_VERTEX_INTEGRATION", "").lower() != "true":
        pytest.skip("Set RUN_VERTEX_INTEGRATION=true to enable live Vertex integration tests")
    if engine.dialect.name != "postgresql":
        pytest.fail("Vertex RAG integration requires DATABASE_URL to reach PostgreSQL")
    settings = get_settings()
    if settings.llm_provider != "vertex" or settings.rag_embedding_provider != "vertex":
        pytest.fail("Set both LLM_PROVIDER and RAG_EMBEDDING_PROVIDER to vertex")
    if not settings.vertex_project_id:
        pytest.fail("Set VERTEX_PROJECT_ID; use a non-production Vertex project")
    if not isinstance(repository, SqlAlchemyRagRepository):
        pytest.fail("Live RAG integration requires the SQLAlchemy repository")


def test_vertex_completion_uses_workload_identity() -> None:
    _require_gcp_integration()
    settings = get_settings()
    model = settings.vertex_model_fast
    provider = VertexAIProvider(
        project_id=settings.vertex_project_id or "",
        location=settings.vertex_location,
        models=frozenset({model}),
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=16,
        max_concurrent_requests=1,
    )

    response = provider.complete(
        LLMRequest(
            model=model,
            task="vertex_integration_smoke_test",
            max_output_tokens=8,
            time_budget_ms=30_000,
            messages=[
                ChatMessage(
                    role=MessageRole.USER,
                    content="Reply with the single word OK to confirm service availability.",
                )
            ],
        )
    )

    assert response.content
    assert response.model == model
    assert response.input_tokens > 0


def test_vertex_embeddings_persist_and_retrieve_with_document_acl() -> None:
    _require_gcp_integration()
    provider = get_embedding_provider()
    tenant_id = str(uuid4())
    document_id = str(uuid4())
    chunk_id = str(uuid4())
    now = utc_now()
    content = (
        "Synthetic retrieval marker: service readiness depends on healthy "
        "database replication and queue processing."
    )
    vector = provider.embed(content, "RETRIEVAL_DOCUMENT")
    document = DocumentRecord(
        id=document_id,
        tenant_id=tenant_id,
        project_id=None,
        environment_id=None,
        scope="unassigned",
        source="synthetic://vertex-integration",
        title="Synthetic Vertex Integration Runbook",
        document_type=DocumentType.RUNBOOK,
        version=1,
        service="integration-test",
        environment="test",
        tags=["synthetic"],
        allowed_roles=["vertex-integration-reader"],
        created_at=now,
        updated_at=now,
        stale_after_days=None,
    )
    chunk = DocumentChunk(
        id=chunk_id,
        document_id=document_id,
        tenant_id=tenant_id,
        ordinal=0,
        content=content,
        metadata={"source": document.source, "title": document.title},
        embedding=vector,
        embedding_provider=provider.name,
        embedding_model=provider.model,
        embedding_version=provider.version,
        embedding_dimensions=provider.dimensions,
    )

    repository.save_document(document, [chunk])
    try:
        permitted = retrieve(
            tenant_id,
            frozenset({"vertex-integration-reader"}),
            query="database replication and queue readiness",
        )
        denied = retrieve(
            tenant_id,
            frozenset({"unprivileged"}),
            query="database replication and queue readiness",
        )
        assert len(permitted.citations) == 1
        assert permitted.citations[0].document_id == document_id
        assert denied.citations == []
        assert provider.dimensions == 768
    finally:
        if not repository.delete_document(tenant_id, document_id, "", ""):
            raise RuntimeError(f"Failed to clean up synthetic RAG document {document_id}")
