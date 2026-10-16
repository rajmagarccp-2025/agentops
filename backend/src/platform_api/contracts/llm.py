"""LLM Gateway request, response, alias, and telemetry contracts."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ModelAlias(StrEnum):
    REASONING_PRIMARY = "reasoning.primary"
    REASONING_FAST = "reasoning.fast"
    REASONING_LONG_CONTEXT = "reasoning.long_context"
    STRUCTURED_OUTPUT = "structured.output"
    EMBEDDING_DEFAULT = "embedding.default"
    RERANKER_DEFAULT = "reranker.default"


class ChatMessage(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1, max_length=100_000)


class LLMRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str = Field(default="general", min_length=1, max_length=100)
    tenant_id: str = Field(default="default", min_length=1, max_length=100)
    model_alias: ModelAlias = ModelAlias.REASONING_PRIMARY
    prompt_version: str = Field(default="v1.0", max_length=50)
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)
    model: str | None = Field(default=None, max_length=150)
    response_format: str = Field(default="text", pattern="^(text|json)$")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=512, ge=1, le=16_384)
    time_budget_ms: int = Field(default=30_000, ge=100, le=300_000)
    token_budget: int = Field(default=8_192, ge=1, le=128_000)
    request_id: str | None = Field(default=None, max_length=100)
    trace_id: str | None = Field(default=None, max_length=100)


class LLMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=150)
    content: str
    structured: dict[str, Any] | None = None
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0.0)
    latency_ms: float = Field(ge=0.0)
    retries: int = Field(ge=0)
    fallback_used: bool = False
