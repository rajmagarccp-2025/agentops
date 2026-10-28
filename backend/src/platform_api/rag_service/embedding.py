import hashlib
import math
from functools import lru_cache
from threading import BoundedSemaphore
from time import monotonic
from typing import Any, Literal, Protocol

import httpx

from platform_api.config import get_settings


class EmbeddingError(RuntimeError):
    pass


class EmbeddingProvider(Protocol):
    name: str
    model: str
    version: str
    dimensions: int

    def embed(
        self, text: str, task_type: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]
    ) -> list[float]: ...


class HashEmbeddingProvider:
    name = "hash"
    model = "sha256-token-hash"
    version = "hash-v2"

    def __init__(self, dimensions: int = 768) -> None:
        self.dimensions = dimensions

    def embed(
        self,
        text: str,
        task_type: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"] = "RETRIEVAL_DOCUMENT",
    ) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % self.dimensions
            vector[index] += 1.0 if digest[2] % 2 else -1.0
        try:
            return normalize_embedding(vector, self.dimensions)
        except ValueError as exc:
            raise EmbeddingError("Hash embedding input produced an invalid vector") from exc


class VertexEmbeddingProvider:
    name = "vertex-ai"
    version = "vertex-embedding-v1"

    def __init__(
        self,
        project_id: str,
        location: str,
        model: str,
        dimensions: int,
        timeout_seconds: float,
        client: Any | None = None,
        max_concurrent_requests: int = 16,
    ) -> None:
        from google import genai
        from google.genai import types

        self.model = model
        self.dimensions = dimensions
        self._timeout_seconds = timeout_seconds
        self._slots = BoundedSemaphore(max_concurrent_requests)
        self._types = types
        self._http_options = types.HttpOptions(timeout=round(timeout_seconds * 1000))
        self._client = client or genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
            http_options=self._http_options,
        )

    def embed(
        self,
        text: str,
        task_type: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"] = "RETRIEVAL_DOCUMENT",
    ) -> list[float]:
        from google.genai import errors

        if not text.strip():
            raise EmbeddingError("Embedding input must not be empty")
        deadline = monotonic() + self._timeout_seconds
        if not self._slots.acquire(timeout=max(0.0, deadline - monotonic())):
            raise EmbeddingError("Vertex embedding concurrency quota is exhausted")
        try:
            remaining_timeout_ms = max(1, round((deadline - monotonic()) * 1000))
            response = self._client.models.embed_content(
                model=self.model,
                contents=text,
                config=self._types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self.dimensions,
                    http_options=self._types.HttpOptions(timeout=remaining_timeout_ms),
                ),
            )
        except errors.APIError as exc:
            raise EmbeddingError(
                f"Vertex embedding request failed ({type(exc).__name__}, status={exc.code})"
            ) from exc
        except (httpx.RequestError, TimeoutError, OSError) as exc:
            raise EmbeddingError(f"Vertex embedding request failed ({type(exc).__name__})") from exc
        finally:
            self._slots.release()

        embeddings = getattr(response, "embeddings", None)
        if not embeddings:
            raise EmbeddingError("Vertex returned no embedding")
        values = getattr(embeddings[0], "values", None)
        if values is None:
            raise EmbeddingError("Vertex returned an embedding without values")
        try:
            return normalize_embedding(values, self.dimensions)
        except ValueError as exc:
            raise EmbeddingError("Vertex returned a malformed embedding") from exc


def normalize_embedding(values: Any, dimensions: int) -> list[float]:
    if not isinstance(values, (list, tuple)) or len(values) != dimensions:
        raise ValueError(f"Embedding must contain exactly {dimensions} values")
    vector: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Embedding values must be numeric")
        normalized_value = float(value)
        if not math.isfinite(normalized_value):
            raise ValueError("Embedding values must be finite")
        vector.append(normalized_value)
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        raise ValueError("Embedding magnitude must be positive")
    return [value / magnitude for value in vector]


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.rag_embedding_provider == "vertex":
        return VertexEmbeddingProvider(
            project_id=settings.vertex_project_id or "",
            location=settings.vertex_location,
            model=settings.vertex_embedding_model,
            dimensions=settings.vertex_embedding_dimensions,
            timeout_seconds=settings.llm_timeout_seconds,
            max_concurrent_requests=settings.vertex_max_concurrent_requests,
        )
    return HashEmbeddingProvider(settings.vertex_embedding_dimensions)


def embed_text(
    text: str,
    task_type: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"] = "RETRIEVAL_DOCUMENT",
) -> list[float]:
    return get_embedding_provider().embed(text, task_type)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))
