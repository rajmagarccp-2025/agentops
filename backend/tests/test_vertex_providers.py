from types import SimpleNamespace

import httpx
import pytest
from google.genai.errors import APIError

from platform_api.llm.gateway import LLMGateway
from platform_api.llm.providers import MockProvider, ProviderCatalog, VertexAIProvider
from platform_api.llm.telemetry import InMemoryLLMTelemetry
from platform_api.llm.types import (
    ChatMessage,
    LLMRequest,
    MessageRole,
    ProviderError,
)
from platform_api.rag_service.embedding import (
    EmbeddingError,
    HashEmbeddingProvider,
    VertexEmbeddingProvider,
    normalize_embedding,
)
from platform_api.security import Principal


class FakeModels:
    def __init__(
        self,
        generation_response: object | None = None,
        embedding_response: object | None = None,
        generation_error: Exception | None = None,
        embedding_error: Exception | None = None,
    ) -> None:
        self.generation_response = generation_response
        self.embedding_response = embedding_response
        self.generation_error = generation_error
        self.embedding_error = embedding_error
        self.generation_calls: list[dict[str, object]] = []
        self.embedding_calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> object:
        self.generation_calls.append(kwargs)
        if self.generation_error:
            raise self.generation_error
        return self.generation_response

    def embed_content(self, **kwargs: object) -> object:
        self.embedding_calls.append(kwargs)
        if self.embedding_error:
            raise self.embedding_error
        return self.embedding_response


def _vertex_llm_response(text: str = "safe answer") -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        usage_metadata=SimpleNamespace(prompt_token_count=12, candidates_token_count=4),
    )


def _request(model: str = "gemini-test") -> LLMRequest:
    return LLMRequest(
        model=model,
        max_output_tokens=10_000,
        time_budget_ms=500,
        messages=[
            ChatMessage(role=MessageRole.SYSTEM, content="Follow the safety policy."),
            ChatMessage(role=MessageRole.USER, content="Summarize synthetic evidence."),
        ],
    )


def _vertex_llm_provider(models: FakeModels) -> VertexAIProvider:
    return VertexAIProvider(
        project_id="synthetic-project",
        location="us-central1",
        models=frozenset({"gemini-test"}),
        timeout_seconds=2,
        max_output_tokens=128,
        max_concurrent_requests=1,
        client=SimpleNamespace(models=models),
    )


def test_vertex_llm_maps_request_and_clamps_output_tokens() -> None:
    models = FakeModels(generation_response=_vertex_llm_response())
    provider = _vertex_llm_provider(models)

    response = provider.complete(_request())

    assert response.content == "safe answer"
    assert response.input_tokens == 12
    assert response.output_tokens == 4
    call = models.generation_calls[0]
    assert call["model"] == "gemini-test"
    config = call["config"]
    assert config.max_output_tokens == 128
    assert config.system_instruction == "Follow the safety policy."
    assert len(config.safety_settings) == 4
    assert config.http_options.timeout == 500
    assert call["contents"][0].role == "user"


def test_vertex_llm_rejects_unapproved_model_without_calling_provider() -> None:
    models = FakeModels(generation_response=_vertex_llm_response())

    with pytest.raises(ProviderError, match="not approved"):
        _vertex_llm_provider(models).complete(_request("unapproved-model"))

    assert models.generation_calls == []


def test_gateway_restricts_model_override_to_the_alias_policy() -> None:
    provider = MockProvider("primary", "approved-model")
    gateway = LLMGateway(
        catalog=ProviderCatalog([provider]),
        telemetry=InMemoryLLMTelemetry(),
        alias_routes={
            "reasoning.primary": [("primary", "approved-model", 0.1, 0.1)],
        },
        max_retries=0,
    )
    principal = Principal(
        subject="synthetic-user",
        tenant_id="synthetic-tenant",
        roles=frozenset(),
        permissions=frozenset({"llm:invoke"}),
    )

    with pytest.raises(ProviderError, match="not approved for this model alias"):
        gateway.complete(_request("unapproved-model"), principal)

    assert provider.calls == 0


@pytest.mark.parametrize(
    "error",
    [TimeoutError("timeout"), httpx.TimeoutException("timeout"), APIError(503, {})],
)
def test_vertex_llm_surfaces_bounded_provider_failures(error: Exception) -> None:
    models = FakeModels(generation_error=error)

    with pytest.raises(ProviderError, match="Vertex AI request failed"):
        _vertex_llm_provider(models).complete(_request())

    assert len(models.generation_calls) == 1


def test_vertex_llm_rejects_malformed_response() -> None:
    class MalformedResponse:
        @property
        def text(self) -> str:
            raise ValueError("no text")

        usage_metadata = SimpleNamespace(prompt_token_count=1, candidates_token_count=1)

    with pytest.raises(ProviderError, match="malformed response"):
        _vertex_llm_provider(FakeModels(generation_response=MalformedResponse())).complete(
            _request()
        )


def test_vertex_concurrency_limit_fails_closed() -> None:
    models = FakeModels(generation_response=_vertex_llm_response())
    provider = _vertex_llm_provider(models)
    assert provider._slots.acquire(blocking=False)
    try:
        with pytest.raises(ProviderError, match="quota is exhausted"):
            provider.complete(_request())
    finally:
        provider._slots.release()
    assert models.generation_calls == []


def test_hash_embedding_is_deterministic_normalized_and_768_dimensional() -> None:
    provider = HashEmbeddingProvider()

    first = provider.embed("synthetic reliability incident")
    second = provider.embed("synthetic reliability incident")

    assert first == second
    assert len(first) == 768
    assert sum(value * value for value in first) == pytest.approx(1.0)


def test_embedding_validation_rejects_wrong_size_and_non_finite_values() -> None:
    with pytest.raises(ValueError, match="exactly 3"):
        normalize_embedding([1.0, 0.0], 3)
    with pytest.raises(ValueError, match="finite"):
        normalize_embedding([float("nan")], 1)


def test_vertex_embedding_sets_retrieval_task_and_normalizes_output() -> None:
    models = FakeModels(
        embedding_response=SimpleNamespace(
            embeddings=[SimpleNamespace(values=[3.0, 4.0])]
        )
    )
    provider = VertexEmbeddingProvider(
        project_id="synthetic-project",
        location="us-central1",
        model="text-embedding-test",
        dimensions=2,
        timeout_seconds=3,
        client=SimpleNamespace(models=models),
    )

    vector = provider.embed("synthetic document", "RETRIEVAL_QUERY")

    assert vector == pytest.approx([0.6, 0.8])
    assert models.embedding_calls[0]["config"].task_type == "RETRIEVAL_QUERY"
    assert models.embedding_calls[0]["config"].output_dimensionality == 2


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (SimpleNamespace(embeddings=[]), "no embedding"),
        (SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0])]), "malformed embedding"),
    ],
)
def test_vertex_embedding_rejects_missing_or_wrong_dimension_response(
    response: object, error: str
) -> None:
    provider = VertexEmbeddingProvider(
        project_id="synthetic-project",
        location="us-central1",
        model="text-embedding-test",
        dimensions=2,
        timeout_seconds=3,
        client=SimpleNamespace(models=FakeModels(embedding_response=response)),
    )

    with pytest.raises(EmbeddingError, match=error):
        provider.embed("synthetic document")


@pytest.mark.parametrize(
    "error",
    [TimeoutError("timeout"), httpx.TimeoutException("timeout"), APIError(429, {})],
)
def test_vertex_embedding_surfaces_outages_and_timeouts(error: Exception) -> None:
    provider = VertexEmbeddingProvider(
        project_id="synthetic-project",
        location="us-central1",
        model="text-embedding-test",
        dimensions=2,
        timeout_seconds=3,
        client=SimpleNamespace(models=FakeModels(embedding_error=error)),
    )

    with pytest.raises(EmbeddingError, match="request failed"):
        provider.embed("synthetic document")
