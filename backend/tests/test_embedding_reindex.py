from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from platform_api.rag_service import reembed
from platform_api.rag_service.embedding import HashEmbeddingProvider
from platform_api.rag_service.models import DocumentChunkModel


def test_reembed_pending_chunks_updates_versioned_embeddings(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    DocumentChunkModel.__table__.create(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(reembed, "SessionLocal", test_session)
    monkeypatch.setattr(
        reembed,
        "get_embedding_provider",
        lambda: HashEmbeddingProvider(dimensions=768),
    )
    with test_session() as session:
        session.add(
            DocumentChunkModel(
                id="legacy-chunk",
                document_id="legacy-document",
                tenant_id="legacy-tenant",
                ordinal=0,
                content="synthetic text to re-embed",
                metadata_json={},
                embedding=None,
                embedding_provider="hash",
                embedding_model="sha256-token-hash",
                embedding_version="hash-v1",
                embedding_dimensions=32,
            )
        )
        session.commit()

    try:
        assert reembed.reembed_pending_chunks(batch_size=10) == 1
        assert reembed.reembed_pending_chunks(batch_size=10) == 0
        with test_session() as session:
            chunk = session.scalar(
                select(DocumentChunkModel).where(DocumentChunkModel.id == "legacy-chunk")
            )

        assert chunk is not None
        assert chunk.embedding is not None
        assert len(chunk.embedding) == 768
        assert chunk.embedding_provider == "hash"
        assert chunk.embedding_version == "hash-v2"
        assert chunk.embedding_dimensions == 768
    finally:
        engine.dispose()
