from collections.abc import Sequence
from threading import BoundedSemaphore
from time import monotonic
from typing import Any

import httpx
from google.genai import types

from platform_api.llm.types import (
    ChatMessage,
    LLMRequest,
    MessageRole,
    ProviderError,
    ProviderResponse,
)


class LLMProvider:
    name: str

    def complete(self, request: LLMRequest) -> ProviderResponse:
        raise NotImplementedError


class MockProvider(LLMProvider):
    health_status = "test-only"

    def __init__(self, name: str, model: str, should_fail: bool = False) -> None:
        self.name = name
        self.model = model
        self.should_fail = should_fail
        self.calls = 0

    def complete(self, request: LLMRequest) -> ProviderResponse:
        self.calls += 1
        if self.should_fail:
            raise ProviderError(f"Mock provider {self.name} is unavailable", retryable=True)
        prompt = _last_user_message(request.messages)
        if request.response_format == "json":
            content = (
                '{"grounded": true, "summary": "Mock response grounded in supplied evidence."}'
            )
        else:
            content = f"Mock analysis for: {prompt[:240]}"
        input_tokens = _estimate_tokens(request.messages)
        output_tokens = _estimate_tokens([ChatMessage(role=MessageRole.ASSISTANT, content=content)])
        return ProviderResponse(
            content=content,
            model=request.model if request.model else self.model,
            input_tokens=input_tokens,
            output_tokens=min(output_tokens, request.max_output_tokens),
        )


class VertexAIProvider(LLMProvider):
    health_status = "not tested"

    def __init__(
        self,
        project_id: str,
        location: str,
        models: frozenset[str],
        timeout_seconds: float,
        max_output_tokens: int,
        max_concurrent_requests: int,
        client: Any | None = None,
    ) -> None:
        from google import genai

        self.name = "vertex-ai"
        self._models = models
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens
        self._slots = BoundedSemaphore(max_concurrent_requests)
        self._client = client or genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
            http_options=types.HttpOptions(timeout=round(timeout_seconds * 1000)),
        )

    def complete(self, request: LLMRequest) -> ProviderResponse:
        from google.genai import errors

        model = request.model
        if not model or model not in self._models:
            raise ProviderError("Requested model is not approved by the Vertex model policy")
        deadline = monotonic() + min(self._timeout_seconds, request.time_budget_ms / 1000)
        if not self._slots.acquire(timeout=max(0.0, deadline - monotonic())):
            raise ProviderError("Vertex AI concurrency quota is exhausted")

        try:
            remaining_timeout_ms = max(1, round((deadline - monotonic()) * 1000))
            system_instruction = "\n\n".join(
                message.content for message in request.messages if message.role.value == "system"
            )
            contents = [
                types.Content(
                    role="model" if message.role.value == "assistant" else "user",
                    parts=[types.Part(text=message.content)],
                )
                for message in request.messages
                if message.role.value != "system"
            ]
            if not contents:
                raise ProviderError("Vertex AI request requires a user or assistant message")

            safety_settings = [
                types.SafetySetting(
                    category=category,
                    threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                )
                for category in (
                    types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                )
            ]
            config = types.GenerateContentConfig(
                system_instruction=system_instruction or None,
                temperature=request.temperature,
                max_output_tokens=min(request.max_output_tokens, self._max_output_tokens),
                response_mime_type=(
                    "application/json" if request.response_format == "json" else None
                ),
                safety_settings=safety_settings,
                http_options=types.HttpOptions(
                    timeout=remaining_timeout_ms
                ),
            )
            response = self._client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except errors.APIError as exc:
            provider_status = exc.code if isinstance(exc.code, int) else None
            raise ProviderError(
                f"Vertex AI request failed ({type(exc).__name__}, status={provider_status})",
                retryable=(
                    provider_status in {408, 429}
                    or (provider_status is not None and provider_status >= 500)
                ),
                status_code=429 if provider_status == 429 else 503,
            ) from exc
        except (httpx.RequestError, TimeoutError, OSError) as exc:
            raise ProviderError(
                f"Vertex AI request failed ({type(exc).__name__})", retryable=True
            ) from exc
        finally:
            self._slots.release()

        try:
            content = response.text
        except ValueError as exc:
            raise ProviderError("Vertex AI returned a malformed response") from exc
        usage = getattr(response, "usage_metadata", None)
        if not isinstance(content, str) or not content.strip() or usage is None:
            raise ProviderError("Vertex AI returned an incomplete response")
        input_tokens = getattr(usage, "prompt_token_count", None)
        output_tokens = getattr(usage, "candidates_token_count", None)
        if (
            not isinstance(input_tokens, int)
            or not isinstance(output_tokens, int)
            or input_tokens < 0
            or output_tokens < 0
        ):
            raise ProviderError("Vertex AI returned malformed usage metadata")
        return ProviderResponse(
            content=content,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


class ProviderCatalog:
    def __init__(self, providers: Sequence[LLMProvider]) -> None:
        self._providers = {provider.name: provider for provider in providers}

    def get(self, name: str) -> LLMProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise ProviderError(f"Unknown provider: {name}") from exc

    def health(self) -> dict[str, str]:
        return {
            name: getattr(provider, "health_status", "not tested")
            for name, provider in self._providers.items()
        }


def _last_user_message(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role.value == "user":
            return message.content
    return messages[-1].content


def _estimate_tokens(messages: list[ChatMessage]) -> int:
    return max(1, sum(len(message.content.split()) for message in messages) // 4)
