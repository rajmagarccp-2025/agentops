from sqlalchemy import select

from platform_api.database import SessionLocal
from platform_api.rag_service.embedding import get_embedding_provider
from platform_api.rag_service.models import DocumentChunkModel


def reembed_pending_chunks(batch_size: int = 100) -> int:
    if not 1 <= batch_size <= 1_000:
        raise ValueError("batch_size must be between 1 and 1000")
    provider = get_embedding_provider()
    with SessionLocal() as session:
        pending = session.execute(
            select(DocumentChunkModel.id, DocumentChunkModel.content)
            .where(DocumentChunkModel.embedding.is_(None))
            .order_by(DocumentChunkModel.id)
            .limit(batch_size)
        ).all()
    if not pending:
        return 0

    vectors = {
        chunk_id: provider.embed(content, "RETRIEVAL_DOCUMENT")
        for chunk_id, content in pending
    }
    with SessionLocal() as session:
        chunks = session.scalars(
            select(DocumentChunkModel).where(
                DocumentChunkModel.id.in_(vectors),
                DocumentChunkModel.embedding.is_(None),
            )
        ).all()
        for chunk in chunks:
            chunk.embedding = vectors[chunk.id]
            chunk.embedding_provider = provider.name
            chunk.embedding_model = provider.model
            chunk.embedding_version = provider.version
            chunk.embedding_dimensions = provider.dimensions
        session.commit()
        return len(chunks)


def main() -> None:
    total = 0
    while count := reembed_pending_chunks():
        total += count
        print(f"Re-embedded {total} document chunks")
    print(f"RAG embedding migration complete: {total} chunks updated")


if __name__ == "__main__":
    main()
