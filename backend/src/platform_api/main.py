from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.responses import JSONResponse

from platform_api.api.agents import router as agents_router
from platform_api.api.ai_query import router as ai_query_router
from platform_api.api.approvals import router as approvals_router
from platform_api.api.audit import router as audit_router
from platform_api.api.auth import router as auth_router
from platform_api.api.changes import router as changes_router
from platform_api.api.cloud_integrations import router as cloud_integrations_router
from platform_api.api.contact import router as contact_router
from platform_api.api.environments import router as environments_router
from platform_api.api.finops import router as finops_router
from platform_api.api.health import router as health_router
from platform_api.api.incidents import router as incidents_router
from platform_api.api.inventory import router as inventory_router
from platform_api.api.invitations import router as invitations_router
from platform_api.api.learning import router as learning_router
from platform_api.api.llmops import gateway_router as llm_gateway_router
from platform_api.api.llmops import router as llmops_router
from platform_api.api.metrics import router as metrics_router
from platform_api.api.onboarding import router as onboarding_router
from platform_api.api.organizations import router as organizations_router
from platform_api.api.projects import router as projects_router
from platform_api.api.rag import router as rag_router
from platform_api.api.remediation import router as remediation_router
from platform_api.api.roles import router as roles_router
from platform_api.api.secrets import router as secrets_router
from platform_api.api.security import router as security_router
from platform_api.api.tools import router as tools_router
from platform_api.config import get_settings
from platform_api.errors import ApplicationError, application_error_handler
from platform_api.logging_config import configure_logging
from platform_api.middleware import RequestIdMiddleware
from platform_api.observability import configure_observability
from platform_api.redis_client import close_redis_client
from platform_api.secrets.cache import close_cache_client
from platform_api.security import _decode_token

settings = get_settings()
configure_logging(settings.log_level)
configure_observability()


class HealthResponse(BaseModel):
    status: str
    service: str = "api"
    version: str = "0.1.0"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await close_redis_client()
    close_cache_client()


app = FastAPI(
    title="AgentOps API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

DEMO_READ_ONLY_ALLOWED_WRITES = {
    ("POST", "/api/v1/auth/switch-context"),
    ("POST", "/api/v1/rag/retrieve"),
    ("POST", "/api/v1/secrets/resolve"),
    ("POST", "/v1/chat/completions"),
    ("POST", "/api/v1/chat/completions"),
    ("POST", "/api/v1/llmops/chat/completions"),
    ("POST", "/api/v1/llmops/models/test-credentials"),
}


@app.middleware("http")
async def enforce_demo_read_only(request: Request, call_next):
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            claims = _decode_token(token)
        except HTTPException:
            claims = {}
        if claims.get("read_only_demo") is True:
            method = request.method.upper()
            if (
                method not in {"GET", "HEAD", "OPTIONS"}
                and (
                    method,
                    request.url.path,
                )
                not in DEMO_READ_ONLY_ALLOWED_WRITES
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Demo mode is read-only; data-changing actions are disabled.",
                        "code": "demo_read_only",
                    },
                )
    return await call_next(request)


origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)
app.add_exception_handler(ApplicationError, application_error_handler)
app.include_router(health_router, prefix="/api/v1")
app.include_router(inventory_router, prefix="/api/v1")
app.include_router(incidents_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(onboarding_router, prefix="/api/v1")
app.include_router(organizations_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(environments_router, prefix="/api/v1")
app.include_router(invitations_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(roles_router, prefix="/api/v1")
app.include_router(ai_query_router, prefix="/api/v1")
app.include_router(changes_router, prefix="/api/v1")
app.include_router(finops_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(approvals_router, prefix="/api/v1")
app.include_router(tools_router, prefix="/api/v1")
app.include_router(llmops_router, prefix="/api/v1")
app.include_router(llm_gateway_router)
app.include_router(learning_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(rag_router, prefix="/api/v1")
app.include_router(remediation_router, prefix="/api/v1")
app.include_router(security_router, prefix="/api/v1")
app.include_router(contact_router, prefix="/api/v1")
app.include_router(cloud_integrations_router, prefix="/api/v1")
app.include_router(secrets_router, prefix="/api/v1")
app.include_router(organizations_router, prefix="/api/v1/tenants", tags=["tenants"])


@app.get("/health", response_model=dict[str, str], tags=["health"])
async def root_health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health", response_model=dict[str, str], tags=["health"])
async def api_health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="api", version="0.1.0")
