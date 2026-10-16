from time import perf_counter
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from platform_api.observability import (
    extract_w3c_context,
    inject_w3c_context,
    record_request,
    span,
)


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
        request_id = headers.get("x-request-id", str(uuid4()))
        correlation_id = headers.get("x-correlation-id", str(uuid4()))
        tenant_id = headers.get("x-tenant-id", "tenant-default")
        user_id = headers.get("x-user-id", "user-anonymous")
        workflow_id = headers.get("x-workflow-id", "wf-default")
        agent_run_id = headers.get("x-agent-run-id", "run-default")
        incident_id = headers.get("x-incident-id", "inc-default")
        service_id = headers.get("x-service-id", "checkout-api")

        # Extract W3C Context
        w3c_carrier = {k: v for k, v in headers.items() if k in ("traceparent", "tracestate")}
        extracted_context = extract_w3c_context(w3c_carrier)

        scope_state = {
            **scope.get("state", {}),
            "request_id": request_id,
            "correlation_id": correlation_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "workflow_id": workflow_id,
            "agent_run_id": agent_run_id,
            "incident_id": incident_id,
            "service_id": service_id,
            "w3c_context": extracted_context,
        }
        scope["state"] = scope_state
        started = perf_counter()

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                resp_headers = list(message.get("headers", []))
                resp_headers.append((b"x-request-id", request_id.encode()))
                resp_headers.append((b"x-correlation-id", correlation_id.encode()))
                # Inject W3C Context
                outbound_carrier: dict[str, str] = {}
                inject_w3c_context(outbound_carrier)
                for k, v in outbound_carrier.items():
                    resp_headers.append((k.encode(), v.encode()))
                message["headers"] = resp_headers
            await send(message)

        route = scope.get("path", "unknown")
        span_attrs = {
            "http.method": scope.get("method", ""),
            "http.route": route,
            "request_id": request_id,
            "correlation_id": correlation_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "workflow_id": workflow_id,
            "agent_run_id": agent_run_id,
            "incident_id": incident_id,
            "service_id": service_id,
        }

        with span("http.request", span_attrs) as request_span:
            await self.app(scope, receive, send_with_request_id)
            duration_ms = (perf_counter() - started) * 1000
            if request_span is not None:
                request_span.set_attribute("http.duration_ms", duration_ms)
            record_request(scope.get("method", ""), route, 200, duration_ms)
