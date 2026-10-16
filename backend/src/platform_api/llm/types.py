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
    pass


__all__ = [
    "ChatMessage",
    "LLMRequest",
    "LLMResponse",
    "MessageRole",
    "ModelAlias",
    "ProviderError",
    "ProviderResponse",
]
