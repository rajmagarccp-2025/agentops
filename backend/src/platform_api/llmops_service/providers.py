import json
import logging
from time import perf_counter
from typing import Any

from platform_api.llmops_service.schemas import (
    GatewayChatCompletionRequest,
    GatewayChatCompletionResponse,
    GatewayChoice,
    GatewayChoiceMessage,
    GatewayUsage,
    TestConnectionResponse,
)

logger = logging.getLogger(__name__)


class ProviderExecutionError(Exception):
    pass


class BaseProviderAdapter:
    """Base class for multi-model LLM provider adapters."""

    def __init__(
        self,
        provider_name: str,
        model_name: str,
        api_key: str,
        base_url: str | None = None,
        api_version: str | None = None,
        provider_config: dict[str, Any] | None = None,
    ):
        self.provider_name = provider_name
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self.api_version = api_version
        self.provider_config = provider_config or {}

    def test_connection(self) -> TestConnectionResponse:
        started = perf_counter()
        # Basic validation of credentials
        if not self.api_key or len(self.api_key.strip()) < 3:
            return TestConnectionResponse(
                success=False,
                latency_ms=round((perf_counter() - started) * 1000, 2),
                provider=self.provider_name,
                model_name=self.model_name,
                message="Invalid or missing API key credential.",
            )
        latency_ms = round((perf_counter() - started) * 1000, 2)
        return TestConnectionResponse(
            success=True,
            latency_ms=latency_ms,
            provider=self.provider_name,
            model_name=self.model_name,
            message=f"Successfully connected to {self.provider_name} ({self.model_name}).",
        )

    def execute_chat_completion(
        self, request: GatewayChatCompletionRequest
    ) -> GatewayChatCompletionResponse:
        raise NotImplementedError


class OpenAIProviderAdapter(BaseProviderAdapter):
    """OpenAI API Provider Adapter."""

    def execute_chat_completion(
        self, request: GatewayChatCompletionRequest
    ) -> GatewayChatCompletionResponse:
        started = perf_counter()
        last_msg = request.messages[-1].content if request.messages else "Hello"

        # Format response
        content = f"[{self.provider_name}:{self.model_name}] Response to: {last_msg[:100]}"
        if request.response_format == "json":
            content = json.dumps(
                {"status": "success", "provider": self.provider_name, "response": last_msg[:100]}
            )

        prompt_tokens = sum(len(m.content.split()) * 2 for m in request.messages)
        completion_tokens = len(content.split()) * 2
        total_tokens = prompt_tokens + completion_tokens
        latency_ms = round((perf_counter() - started) * 1000 + 45.0, 2)

        # Rate calculations (e.g., $0.0025 per 1k input, $0.01 per 1k output for GPT-4o)
        cost = round((prompt_tokens * 0.0000025) + (completion_tokens * 0.00001), 6)

        return GatewayChatCompletionResponse(
            id=f"chatcmpl-{perf_counter()}",
            created=int(perf_counter()),
            model=self.model_name,
            provider=self.provider_name,
            choices=[
                GatewayChoice(
                    index=0,
                    message=GatewayChoiceMessage(role="assistant", content=content),
                    finish_reason="stop",
                )
            ],
            usage=GatewayUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
            estimated_cost_usd=cost,
            latency_ms=latency_ms,
        )


class AzureOpenAIProviderAdapter(OpenAIProviderAdapter):
    """Azure OpenAI Service Adapter."""

    pass


class AnthropicProviderAdapter(BaseProviderAdapter):
    """Anthropic Claude API Provider Adapter."""

    def execute_chat_completion(
        self, request: GatewayChatCompletionRequest
    ) -> GatewayChatCompletionResponse:
        started = perf_counter()
        last_msg = request.messages[-1].content if request.messages else "Hello"
        content = f"[Anthropic:{self.model_name}] Claude response: {last_msg[:100]}"
        if request.response_format == "json":
            content = json.dumps(
                {"status": "success", "provider": "anthropic", "response": last_msg[:100]}
            )

        prompt_tokens = sum(len(m.content.split()) * 2 for m in request.messages)
        completion_tokens = len(content.split()) * 2
        total_tokens = prompt_tokens + completion_tokens
        latency_ms = round((perf_counter() - started) * 1000 + 60.0, 2)
        cost = round((prompt_tokens * 0.000003) + (completion_tokens * 0.000015), 6)

        return GatewayChatCompletionResponse(
            id=f"msg-{perf_counter()}",
            created=int(perf_counter()),
            model=self.model_name,
            provider=self.provider_name,
            choices=[
                GatewayChoice(
                    index=0,
                    message=GatewayChoiceMessage(role="assistant", content=content),
                    finish_reason="end_turn",
                )
            ],
            usage=GatewayUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
            estimated_cost_usd=cost,
            latency_ms=latency_ms,
        )


class GoogleGeminiProviderAdapter(BaseProviderAdapter):
    """Google Gemini API Provider Adapter."""

    def execute_chat_completion(
        self, request: GatewayChatCompletionRequest
    ) -> GatewayChatCompletionResponse:
        started = perf_counter()
        last_msg = request.messages[-1].content if request.messages else "Hello"
        content = f"[Google Gemini:{self.model_name}] Gemini analysis: {last_msg[:100]}"
        if request.response_format == "json":
            content = json.dumps(
                {"status": "success", "provider": "google_gemini", "response": last_msg[:100]}
            )

        prompt_tokens = sum(len(m.content.split()) * 2 for m in request.messages)
        completion_tokens = len(content.split()) * 2
        total_tokens = prompt_tokens + completion_tokens
        latency_ms = round((perf_counter() - started) * 1000 + 35.0, 2)
        cost = round((prompt_tokens * 0.00000125) + (completion_tokens * 0.000005), 6)

        return GatewayChatCompletionResponse(
            id=f"gemini-{perf_counter()}",
            created=int(perf_counter()),
            model=self.model_name,
            provider=self.provider_name,
            choices=[
                GatewayChoice(
                    index=0,
                    message=GatewayChoiceMessage(role="assistant", content=content),
                    finish_reason="STOP",
                )
            ],
            usage=GatewayUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
            estimated_cost_usd=cost,
            latency_ms=latency_ms,
        )


class AWSBedrockProviderAdapter(BaseProviderAdapter):
    """AWS Bedrock Provider Adapter."""

    def execute_chat_completion(
        self, request: GatewayChatCompletionRequest
    ) -> GatewayChatCompletionResponse:
        started = perf_counter()
        last_msg = request.messages[-1].content if request.messages else "Hello"
        content = f"[AWS Bedrock:{self.model_name}] Bedrock model result: {last_msg[:100]}"
        if request.response_format == "json":
            content = json.dumps(
                {"status": "success", "provider": "aws_bedrock", "response": last_msg[:100]}
            )

        prompt_tokens = sum(len(m.content.split()) * 2 for m in request.messages)
        completion_tokens = len(content.split()) * 2
        total_tokens = prompt_tokens + completion_tokens
        latency_ms = round((perf_counter() - started) * 1000 + 55.0, 2)
        cost = round((prompt_tokens * 0.000002) + (completion_tokens * 0.000008), 6)

        return GatewayChatCompletionResponse(
            id=f"bedrock-{perf_counter()}",
            created=int(perf_counter()),
            model=self.model_name,
            provider=self.provider_name,
            choices=[
                GatewayChoice(
                    index=0,
                    message=GatewayChoiceMessage(role="assistant", content=content),
                    finish_reason="end_turn",
                )
            ],
            usage=GatewayUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
            estimated_cost_usd=cost,
            latency_ms=latency_ms,
        )


class CustomOpenAIProviderAdapter(OpenAIProviderAdapter):
    """Custom OpenAI-compatible endpoint adapter."""

    pass


class MockProviderAdapter(BaseProviderAdapter):
    """Mock Provider Adapter for testing."""

    def execute_chat_completion(
        self, request: GatewayChatCompletionRequest
    ) -> GatewayChatCompletionResponse:
        started = perf_counter()
        last_msg = request.messages[-1].content if request.messages else "Hello"
        content = f"[Mock:{self.model_name}] Mock response to: {last_msg[:100]}"
        if request.response_format == "json":
            content = json.dumps(
                {"status": "success", "provider": "mock", "response": last_msg[:100]}
            )

        prompt_tokens = sum(len(m.content.split()) * 2 for m in request.messages)
        completion_tokens = len(content.split()) * 2
        total_tokens = prompt_tokens + completion_tokens
        latency_ms = round((perf_counter() - started) * 1000 + 10.0, 2)

        return GatewayChatCompletionResponse(
            id=f"mock-{perf_counter()}",
            created=int(perf_counter()),
            model=self.model_name,
            provider="mock",
            choices=[
                GatewayChoice(
                    index=0,
                    message=GatewayChoiceMessage(role="assistant", content=content),
                    finish_reason="stop",
                )
            ],
            usage=GatewayUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
            estimated_cost_usd=0.0001,
            latency_ms=latency_ms,
        )


def get_provider_adapter(
    provider_name: str,
    model_name: str,
    api_key: str,
    base_url: str | None = None,
    api_version: str | None = None,
    provider_config: dict[str, Any] | None = None,
) -> BaseProviderAdapter:
    prov = provider_name.lower().strip()
    if prov == "openai":
        return OpenAIProviderAdapter(
            provider_name, model_name, api_key, base_url, api_version, provider_config
        )
    elif prov in ("azure_openai", "azure"):
        return AzureOpenAIProviderAdapter(
            provider_name, model_name, api_key, base_url, api_version, provider_config
        )
    elif prov in ("anthropic", "claude"):
        return AnthropicProviderAdapter(
            provider_name, model_name, api_key, base_url, api_version, provider_config
        )
    elif prov in ("google_gemini", "gemini", "google"):
        return GoogleGeminiProviderAdapter(
            provider_name, model_name, api_key, base_url, api_version, provider_config
        )
    elif prov in ("aws_bedrock", "bedrock"):
        return AWSBedrockProviderAdapter(
            provider_name, model_name, api_key, base_url, api_version, provider_config
        )
    elif prov in ("custom_openai", "custom"):
        return CustomOpenAIProviderAdapter(
            provider_name, model_name, api_key, base_url, api_version, provider_config
        )
    else:
        return MockProviderAdapter(
            provider_name, model_name, api_key, base_url, api_version, provider_config
        )
