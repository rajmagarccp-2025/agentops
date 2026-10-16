from typing import Protocol

from platform_api.rag_service.schemas import DocumentChunk


class Reranker(Protocol):
    def rerank(
        self, query: str, chunks: list[tuple[float, DocumentChunk]]
    ) -> list[tuple[float, DocumentChunk]]: ...


class DefaultCosineReranker:
    def rerank(
        self, query: str, chunks: list[tuple[float, DocumentChunk]]
    ) -> list[tuple[float, DocumentChunk]]:
        # Default pass-through reranker maintaining similarity scores
        return sorted(chunks, key=lambda item: item[0], reverse=True)
