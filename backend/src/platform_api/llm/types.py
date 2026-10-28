"""LLM Gateway types and contracts re-exported from platform_api.contracts.llm."""

from pydantic import BaseModel

from platform_api.contracts.llm import (
    ChatMessage,
    LLMRequest,
    LLMResponse,
    MessageRole,
    ModelAlias,
)


class ProviderResponse(BaseModel):
    content: str
    model: str
    input_tokens: int
    output_tokens: int


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int = 503,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


__all__ = [
    "ChatMessage",
    "LLMRequest",
    "LLMResponse",
    "MessageRole",
    "ModelAlias",
    "ProviderError",
    "ProviderResponse",
]
