from time import perf_counter
from uuid import uuid4

from platform_api.config import get_settings
from platform_api.llm.providers import MockProvider, ProviderCatalog, VertexAIProvider
from platform_api.llm.quota import (
    AllowAllTenantQuota,
    RedisTenantQuota,
    TenantQuota,
    TenantQuotaUnavailable,
    TenantRateLimitExceeded,
    TenantTokenBudgetExceeded,
)
from platform_api.llm.telemetry import InMemoryLLMTelemetry, create_event
from platform_api.llm.types import LLMRequest, LLMResponse, ModelAlias, ProviderError
from platform_api.observability import increment, record_llm_metrics, span
from platform_api.secrets.cache import get_cache_client
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
        alias_routes: dict[str, list[tuple[str, str, float, float]]] | None = None,
        quota: TenantQuota | None = None,
        max_input_tokens: int = 32_768,
        max_output_tokens: int = 8_192,
        max_total_tokens: int = 40_960,
    ) -> None:
        self.catalog = catalog
        self.telemetry = telemetry
        self._custom_routes = routes is not None
        self.routes = routes or [("mock-primary", 0.15, 0.60), ("mock-fallback", 0.08, 0.30)]
        self.max_retries = max_retries
        self.alias_routes = alias_routes or ALIAS_ROUTING_MAP
        self.quota = quota or AllowAllTenantQuota()
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.max_total_tokens = max_total_tokens

    def complete(self, request: LLMRequest, principal: Principal) -> LLMResponse:
        if "llm:invoke" not in principal.permissions and "*" not in principal.permissions:
            increment("llm.requests.denied")
            raise ProviderError(
                "Caller lacks permission to invoke the LLM gateway", status_code=403
            )
        if not principal.tenant_id:
            increment("llm.requests.denied")
            raise ProviderError("Authenticated tenant identity is required", status_code=403)
        if request.tenant_id not in {"default", principal.tenant_id}:
            increment("llm.requests.denied")
            raise ProviderError(
                "Request tenant does not match authenticated tenant", status_code=403
            )

        alias_key = (
            request.model_alias.value
            if hasattr(request.model_alias, "value")
            else str(request.model_alias)
        )
        if self._custom_routes:
            route_list = [(r[0], "mock-model", r[1], r[2]) for r in self.routes]
        else:
            route_list = self.alias_routes.get(
                alias_key, [(r[0], "mock-model", r[1], r[2]) for r in self.routes]
            )
        if not route_list:
            increment("llm.requests.rejected")
            raise ProviderError("No model route is configured for this alias", status_code=400)
        if request.model and not self._custom_routes:
            allowed_models = {target_model for _, target_model, _, _ in route_list}
            if request.model not in allowed_models:
                increment("llm.requests.failed")
                raise ProviderError(
                    "Requested model is not approved for this model alias", status_code=400
                )
            route_list = [route for route in route_list if route[1] == request.model]

        request_id = request.request_id or str(uuid4())
        started = perf_counter()
        total_retries = 0
        estimated_input_tokens = sum(
            len(message.content.encode("utf-8")) for message in request.messages
        )
        output_limit = min(request.max_output_tokens, self.max_output_tokens)
        total_token_limit = min(request.token_budget, self.max_total_tokens)
        if estimated_input_tokens > self.max_input_tokens:
            increment("llm.requests.rejected")
            raise ProviderError(
                "Estimated input exceeds the configured token limit", status_code=413
            )
        if estimated_input_tokens + output_limit > total_token_limit:
            increment("llm.requests.rejected")
            raise ProviderError("Input and output exceed the request token budget", status_code=400)
        reserved_tokens = estimated_input_tokens + output_limit
        last_error: ProviderError | None = None
        last_provider = ""
        last_model = ""
        last_fallback = False
        last_input_tokens = 0
        last_output_tokens = 0
        last_estimated_cost_usd = 0.0

        try:
            self.quota.reserve(principal.tenant_id, reserved_tokens)
        except TenantRateLimitExceeded as exc:
            increment("llm.requests.rate_limited")
            raise ProviderError(str(exc), status_code=429) from exc
        except TenantTokenBudgetExceeded as exc:
            increment("llm.requests.budget_exceeded")
            raise ProviderError(str(exc), status_code=429) from exc
        except TenantQuotaUnavailable as exc:
            increment("llm.requests.quota_unavailable")
            raise ProviderError(
                "Tenant usage quota service is unavailable", status_code=503
            ) from exc

        quota_reserved = True
        try:
            for route_index, (provider_name, target_model, input_rate, output_rate) in enumerate(
                route_list
            ):
                provider = self.catalog.get(provider_name)
                last_provider = provider.name
                approved_model = request.model or target_model
                last_model = approved_model
                last_fallback = route_index > 0
                for attempt in range(self.max_retries + 1):
                    remaining_budget_ms = request.time_budget_ms - round(
                        (perf_counter() - started) * 1000
                    )
                    if remaining_budget_ms <= 0:
                        last_error = ProviderError("LLM request exceeded its time budget")
                        break
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
                            req_copy = request.model_copy(
                                update={
                                    "tenant_id": principal.tenant_id,
                                    "model": approved_model,
                                    "max_output_tokens": output_limit,
                                    "token_budget": total_token_limit,
                                    "time_budget_ms": remaining_budget_ms,
                                }
                            )
                            result = provider.complete(req_copy)
                        latency_ms = round((perf_counter() - started) * 1000, 2)
                        if latency_ms > request.time_budget_ms:
                            raise ProviderError("LLM provider exceeded the request time budget")
                        if result.input_tokens > estimated_input_tokens:
                            raise ProviderError("Provider usage exceeded the reserved input budget")
                        if result.input_tokens < 0 or result.output_tokens < 0:
                            raise ProviderError("Provider returned invalid token usage")
                        if result.output_tokens > output_limit:
                            raise ProviderError("Provider usage exceeded the output token limit")
                        if result.model != approved_model:
                            raise ProviderError(
                                "Provider returned a model outside the approved route"
                            )

                        actual_tokens = result.input_tokens + result.output_tokens
                        last_input_tokens = result.input_tokens
                        last_output_tokens = result.output_tokens
                        last_estimated_cost_usd = round(
                            result.input_tokens * input_rate / 1_000_000
                            + result.output_tokens * output_rate / 1_000_000,
                            8,
                        )
                        try:
                            self.quota.settle(
                                principal.tenant_id,
                                reserved_tokens,
                                actual_tokens,
                            )
                        except TenantQuotaUnavailable as exc:
                            raise ProviderError(
                                "Tenant usage quota accounting is unavailable"
                            ) from exc
                        quota_reserved = False
                        content = result.content
                        structured = _parse_structured(content, request.response_format)
                        response = LLMResponse(
                            request_id=request_id,
                            provider=provider.name,
                            model=result.model,
                            content=content,
                            structured=structured,
                            input_tokens=result.input_tokens,
                            output_tokens=result.output_tokens,
                            total_tokens=actual_tokens,
                            estimated_cost_usd=last_estimated_cost_usd,
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
                        last_error = exc
                        increment("llm.requests.failed")
                        if not exc.retryable:
                            break
                        if attempt < self.max_retries:
                            total_retries += 1
                            continue
                        break
                if last_error is not None and not last_error.retryable:
                    break

            if quota_reserved:
                quota_reserved = False
                try:
                    self.quota.release(principal.tenant_id, reserved_tokens)
                except TenantQuotaUnavailable as exc:
                    increment("llm.requests.quota_unavailable")
                    raise ProviderError(
                        "Tenant usage quota accounting is unavailable"
                    ) from exc
            self.telemetry.record(
                create_event(
                    request_id=request_id,
                    tenant_id=principal.tenant_id,
                    subject=principal.subject,
                    provider=last_provider or "none",
                    model=last_model or "none",
                    task=request.task,
                    input_tokens=last_input_tokens,
                    output_tokens=last_output_tokens,
                    estimated_cost_usd=last_estimated_cost_usd,
                    latency_ms=round((perf_counter() - started) * 1000, 2),
                    retries=total_retries,
                    fallback_used=last_fallback,
                    error=(
                        f"provider_error:{last_error.status_code}"
                        if last_error
                        else "no_route"
                    ),
                )
            )
            increment("llm.requests.failed")
            raise ProviderError("No configured LLM provider completed the request") from last_error
        except ProviderError:
            if quota_reserved:
                quota_reserved = False
                try:
                    self.quota.release(principal.tenant_id, reserved_tokens)
                except TenantQuotaUnavailable as exc:
                    increment("llm.requests.quota_unavailable")
                    raise ProviderError(
                        "Tenant usage quota accounting is unavailable"
                    ) from exc
            raise


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
    if settings.llm_provider == "vertex":
        models = {
            settings.vertex_model_reasoning,
            settings.vertex_model_fast,
            settings.vertex_model_long_context,
            settings.vertex_model_structured,
        }
        provider = VertexAIProvider(
            project_id=settings.vertex_project_id or "",
            location=settings.vertex_location,
            models=frozenset(models),
            timeout_seconds=settings.llm_timeout_seconds,
            max_output_tokens=settings.vertex_max_output_tokens,
            max_concurrent_requests=settings.vertex_max_concurrent_requests,
        )
        catalog = ProviderCatalog([provider])
        alias_routes = {
            ModelAlias.REASONING_PRIMARY.value: [
                ("vertex-ai", settings.vertex_model_reasoning, 0.15, 0.60),
                ("vertex-ai", settings.vertex_model_fast, 0.08, 0.30),
            ],
            ModelAlias.REASONING_FAST.value: [
                ("vertex-ai", settings.vertex_model_fast, 0.05, 0.15)
            ],
            ModelAlias.REASONING_LONG_CONTEXT.value: [
                ("vertex-ai", settings.vertex_model_long_context, 0.30, 1.20)
            ],
            ModelAlias.STRUCTURED_OUTPUT.value: [
                ("vertex-ai", settings.vertex_model_structured, 0.10, 0.40)
            ],
            ModelAlias.EMBEDDING_DEFAULT.value: [
                ("vertex-ai", settings.vertex_model_fast, 0.01, 0.01)
            ],
            ModelAlias.RERANKER_DEFAULT.value: [
                ("vertex-ai", settings.vertex_model_fast, 0.02, 0.02)
            ],
        }
    else:
        catalog = ProviderCatalog(
            [
                MockProvider("mock-primary", "mock-reasoner-v1"),
                MockProvider("mock-fallback", "mock-reasoner-fallback"),
            ]
        )
        alias_routes = None
    quota: TenantQuota
    if settings.app_env.lower() == "production":
        quota = RedisTenantQuota(
            get_cache_client(),
            requests_per_minute=settings.llm_tenant_requests_per_minute,
            daily_token_budget=settings.llm_tenant_daily_token_budget,
        )
    else:
        quota = AllowAllTenantQuota()
    return LLMGateway(
        catalog=catalog,
        telemetry=InMemoryLLMTelemetry(),
        routes=None,
        max_retries=settings.llm_max_retries,
        alias_routes=alias_routes,
        quota=quota,
        max_input_tokens=settings.llm_max_input_tokens,
        max_output_tokens=settings.llm_max_output_tokens,
        max_total_tokens=settings.llm_max_total_tokens,
    )
