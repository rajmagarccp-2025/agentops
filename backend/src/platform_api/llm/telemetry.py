from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class LLMEvent:
    request_id: str
    tenant_id: str
    subject: str
    provider: str
    model: str
    task: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    latency_ms: float
    retries: int
    fallback_used: bool
    created_at: datetime
    error: str | None = None
    metadata: dict[str, Any] | None = None


class InMemoryLLMTelemetry:
    def __init__(self) -> None:
        self.events: list[LLMEvent] = []

    def record(self, event: LLMEvent) -> None:
        self.events.append(event)


def create_event(
    *,
    request_id: str,
    tenant_id: str,
    subject: str,
    provider: str,
    model: str,
    task: str,
    input_tokens: int,
    output_tokens: int,
    estimated_cost_usd: float,
    latency_ms: float,
    retries: int,
    fallback_used: bool,
    error: str | None = None,
) -> LLMEvent:
    return LLMEvent(
        request_id=request_id,
        tenant_id=tenant_id,
        subject=subject,
        provider=provider,
        model=model,
        task=task,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost_usd,
        latency_ms=latency_ms,
        retries=retries,
        fallback_used=fallback_used,
        created_at=datetime.now(UTC),
        error=error,
    )
