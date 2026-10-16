import re
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Span, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from platform_api.config import get_settings

_metrics: Counter[str] = Counter()
_tracer: trace.Tracer | None = None
_propagator = TraceContextTextMapPropagator()

# Secret Redaction Regexes for Logs and Traces
SECRET_PATTERNS = [
    re.compile(
        r"(?i)(bearer\s+|token\s*[:=]\s*|password\s*[:=]\s*|secret\s*[:=]\s*|api[_-]?key\s*[:=]\s*)([a-zA-Z0-9_\-\.]{8,})"
    ),
    re.compile(r"(?i)(AKIA[0-9A-Z]{16})"),
    re.compile(r"(?i)(eyJ[a-zA-Z0-9_\-]*\.[a-zA-Z0-9_\-]*\.[a-zA-Z0-9_\-]*)"),  # JWT
]

PROPAGATION_KEYS = [
    "request_id",
    "correlation_id",
    "trace_id",
    "tenant_id",
    "user_id",
    "workflow_id",
    "agent_run_id",
    "agent_id",
    "incident_id",
    "service_id",
    "tool_call_id",
    "llm_request_id",
    "approval_id",
    "remediation_id",
    "source_event_id",
    "document_id",
]


def redact_sensitive_value(value: str) -> str:
    """Sanitize secrets, tokens, and credentials from telemetry data."""
    if not isinstance(value, str):
        return value
    sanitized = value
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
    return sanitized


def configure_observability() -> None:
    global _tracer
    import os
    import sys

    settings = get_settings()
    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.otel_service_name})
    )
    is_test_env = bool(
        "pytest" in sys.modules
        or any("pytest" in arg for arg in sys.argv)
        or os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("OTEL_SDK_DISABLED", "").lower() in ("true", "1")
        or settings.app_env == "test"
    )
    if settings.otel_exporter_otlp_endpoint and not is_test_env:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
            )
        except Exception:
            pass
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(settings.otel_service_name)


def increment(metric: str, value: int = 1) -> None:
    _metrics[metric] += value


def metrics_text() -> str:
    return "".join(
        f"platform_{name.replace('.', '_')} {value}\n" for name, value in sorted(_metrics.items())
    )


def metrics_snapshot() -> dict[str, int]:
    response_errors = sum(
        value
        for key, value in _metrics.items()
        if key.startswith("http.responses.") and key.rsplit(".", 1)[-1].startswith("5")
    )
    tool_errors = sum(
        value
        for key, value in _metrics.items()
        if key.startswith("mcp.tool.") and key.endswith(".errors")
    )
    snapshot = {
        "http_requests_total": _metrics.get("http.requests.total", 0),
        "http_5xx_responses_total": response_errors,
        "llm_requests_total": _metrics.get("llm.requests.total", 0),
        "llm_prompt_tokens_total": _metrics.get("llm.tokens.prompt", 0),
        "llm_completion_tokens_total": _metrics.get("llm.tokens.completion", 0),
        "tool_executions_total": _metrics.get("mcp.tool_executions.total", 0),
        "tool_errors_total": tool_errors,
        "workflow_executions_total": _metrics.get("workflow.executions.total", 0),
    }
    return snapshot


def extract_w3c_context(carrier: dict[str, str]) -> trace.Context:
    """Extract W3C tracecontext propagation headers (traceparent, tracestate)."""
    return _propagator.extract(carrier=carrier)


def inject_w3c_context(carrier: dict[str, str], context: trace.Context | None = None) -> None:
    """Inject W3C tracecontext headers (traceparent, tracestate) into outbound requests."""
    _propagator.inject(carrier=carrier, context=context)


@contextmanager
def span(name: str, attributes: dict[str, object] | None = None) -> Iterator[Span | None]:
    tracer = _tracer or trace.get_tracer("agentic-platform")
    with tracer.start_as_current_span(name) as current:
        if attributes:
            for key, value in attributes.items():
                if any(
                    sec in key.lower()
                    for sec in ["secret", "password", "token", "key", "authorization"]
                ):
                    attribute_value = "[REDACTED]"
                else:
                    str_val = str(value)
                    attribute_value = (
                        redact_sensitive_value(str_val) if isinstance(value, str) else value
                    )
                current.set_attribute(key, attribute_value)
        try:
            yield current
        except Exception as exc:
            current.record_exception(exc)
            current.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


def record_request(method: str, route: str, status_code: int, duration_ms: float) -> None:
    increment("http.requests.total")
    increment(f"http.responses.{status_code}")
    increment(f"http.route.{method.lower()}.{route}.total")
    _metrics[f"http.duration_ms.{route}"] += int(duration_ms)


def record_llm_metrics(
    model_alias: str, tokens_prompt: int, tokens_completion: int, cost_usd: float, latency_ms: float
) -> None:
    increment("llm.requests.total")
    increment(f"llm.model.{model_alias}.requests.total")
    increment("llm.tokens.prompt", tokens_prompt)
    increment("llm.tokens.completion", tokens_completion)
    increment("llm.tokens.total", tokens_prompt + tokens_completion)
    _metrics[f"llm.cost_usd.{model_alias}"] += int(cost_usd * 10000)
    _metrics[f"llm.latency_ms.{model_alias}"] += int(latency_ms)


def record_tool_execution(tool_name: str, risk: str, success: bool, duration_ms: float) -> None:
    increment("mcp.tool_executions.total")
    increment(f"mcp.tool.{tool_name}.total")
    increment(f"mcp.risk.{risk}.total")
    if not success:
        increment(f"mcp.tool.{tool_name}.errors")
    _metrics[f"mcp.duration_ms.{tool_name}"] += int(duration_ms)


def record_workflow_metrics(workflow_id: str, status: str, duration_ms: float) -> None:
    increment("workflow.executions.total")
    increment(f"workflow.status.{status}")
    _metrics[f"workflow.duration_ms.{workflow_id}"] += int(duration_ms)


def record_alert(name: str, severity: str) -> None:
    """Count operational alerts using bounded, low-cardinality labels."""
    if severity not in {"warning", "critical"}:
        raise ValueError(f"Unsupported alert severity: {severity}")
    increment(f"alerts.{severity}.{name}")
