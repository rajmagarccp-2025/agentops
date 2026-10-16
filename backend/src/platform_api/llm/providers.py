from collections.abc import Sequence

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
    def __init__(self, name: str, model: str, should_fail: bool = False) -> None:
        self.name = name
        self.model = model
        self.should_fail = should_fail
        self.calls = 0

    def complete(self, request: LLMRequest) -> ProviderResponse:
        self.calls += 1
        if self.should_fail:
            raise ProviderError(f"Mock provider {self.name} is unavailable")
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


class ProviderCatalog:
    def __init__(self, providers: Sequence[LLMProvider]) -> None:
        self._providers = {provider.name: provider for provider in providers}

    def get(self, name: str) -> LLMProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise ProviderError(f"Unknown provider: {name}") from exc

    def health(self) -> dict[str, str]:
        return {name: "configured" for name in self._providers}


def _last_user_message(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role.value == "user":
            return message.content
    return messages[-1].content


def _estimate_tokens(messages: list[ChatMessage]) -> int:
    return max(1, sum(len(message.content.split()) for message in messages) // 4)
