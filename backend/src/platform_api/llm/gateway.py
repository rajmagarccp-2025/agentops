from time import perf_counter
from uuid import uuid4

from platform_api.config import get_settings
from platform_api.llm.providers import MockProvider, ProviderCatalog
from platform_api.llm.telemetry import InMemoryLLMTelemetry, create_event
from platform_api.llm.types import LLMRequest, LLMResponse, ModelAlias, ProviderError
from platform_api.observability import increment, record_llm_metrics, span
from platform_api.security import Principal

ALIAS_ROUTING_MAP: dict[str, list[tuple[str, str, float, float]]] = {
    ModelAlias.REASONING_PRIMARY.value: [
        ("mock-primary", "mock-reasoner-v1", 0.15, 0.60),
        ("mock-fallback", "mock-reasoner-fallback", 0.08, 0.30),
    ],
    ModelAlias.REASONING_FAST.value: [("mock-primary", "mock-fast-v1", 0.05, 0.15)],
    ModelAlias.REASONING_LONG_CONTEXT.value: [("mock-primary", "mock-longctx-v1", 0.30, 1.20)],
    ModelAlias.STRUCTURED_OUTPUT.value: [("mock-primary", "mock-structured-v1", 0.10, 0.40)],
    ModelAlias.EMBEDDING_DEFAULT.value: [("mock-primary", "mock-embed-v1", 0.01, 0.01)],
    ModelAlias.RERANKER_DEFAULT.value: [("mock-primary", "mock-rerank-v1", 0.02, 0.02)],
}


class LLMGateway:
    def __init__(
        self,
        catalog: ProviderCatalog,
        telemetry: InMemoryLLMTelemetry,
        routes: list[tuple[str, float, float]] | None = None,
        max_retries: int = 1,
    ) -> None:
        self.catalog = catalog
        self.telemetry = telemetry
        self._custom_routes = routes is not None
        self.routes = routes or [("mock-primary", 0.15, 0.60), ("mock-fallback", 0.08, 0.30)]
        self.max_retries = max_retries

    def complete(self, request: LLMRequest, principal: Principal) -> LLMResponse:
        request_id = request.request_id or str(uuid4())
        started = perf_counter()
        errors: list[str] = []
        total_retries = 0

        # Use alias routes when configured; otherwise fall back to the default routes.
        alias_key = (
            request.model_alias.value
            if hasattr(request.model_alias, "value")
            else str(request.model_alias)
        )
        if self._custom_routes:
            route_list = [(r[0], "mock-model", r[1], r[2]) for r in self.routes]
        else:
            route_list = ALIAS_ROUTING_MAP.get(
                alias_key, [(r[0], "mock-model", r[1], r[2]) for r in self.routes]
            )

        for route_index, (provider_name, target_model, input_rate, output_rate) in enumerate(
            route_list
        ):
            provider = self.catalog.get(provider_name)
            for attempt in range(self.max_retries + 1):
                try:
                    with span(
                        "llm.provider.call",
                        {
                            "llm.provider": provider.name,
                            "llm.task": request.task,
                            "llm.alias": alias_key,
                            "llm.prompt_version": request.prompt_version,
                        },
                    ):
                        model_override = request.model or target_model
                        req_copy = request.model_copy(update={"model": model_override})
                        result = provider.complete(req_copy)
                    latency_ms = round((perf_counter() - started) * 1000, 2)

                    # Timeout check against time_budget_ms
                    if latency_ms > request.time_budget_ms:
                        raise ProviderError(
                            f"LLM request timed out after {latency_ms}ms "
                            f"(budget: {request.time_budget_ms}ms)"
                        )

                    cost = round(
                        result.input_tokens * input_rate / 1_000_000
                        + result.output_tokens * output_rate / 1_000_000,
                        8,
                    )
                    response = LLMResponse(
                        request_id=request_id,
                        provider=provider.name,
                        model=result.model,
                        content=result.content,
                        structured=_parse_structured(result.content, request.response_format),
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                        total_tokens=result.input_tokens + result.output_tokens,
                        estimated_cost_usd=cost,
                        latency_ms=latency_ms,
                        retries=total_retries,
                        fallback_used=route_index > 0,
                    )
                    self.telemetry.record(
                        create_event(
                            request_id=request_id,
                            tenant_id=principal.tenant_id,
                            subject=principal.subject,
                            provider=response.provider,
                            model=response.model,
                            task=request.task,
                            input_tokens=response.input_tokens,
                            output_tokens=response.output_tokens,
                            estimated_cost_usd=response.estimated_cost_usd,
                            latency_ms=response.latency_ms,
                            retries=response.retries,
                            fallback_used=response.fallback_used,
                        )
                    )
                    record_llm_metrics(
                        alias_key,
                        response.input_tokens,
                        response.output_tokens,
                        response.estimated_cost_usd,
                        response.latency_ms,
                    )
                    increment("llm.requests.success")
                    return response
                except ProviderError as exc:
                    errors.append(str(exc))
                    if attempt < self.max_retries:
                        total_retries += 1
                        continue
                    break
                increment("llm.requests.failed")
        raise ProviderError("All configured LLM routes failed: " + "; ".join(errors))


def _parse_structured(content: str, response_format: str) -> dict[str, object] | None:
    if response_format != "json":
        return None
    import json

    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProviderError("Provider returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise ProviderError("Provider returned a non-object JSON value")
    return value


def default_gateway() -> LLMGateway:
    settings = get_settings()
    catalog = ProviderCatalog(
        [
            MockProvider("mock-primary", "mock-reasoner-v1"),
            MockProvider("mock-fallback", "mock-reasoner-fallback"),
        ]
    )
    return LLMGateway(
        catalog=catalog,
        telemetry=InMemoryLLMTelemetry(),
        routes=None,
        max_retries=settings.llm_max_retries,
    )
