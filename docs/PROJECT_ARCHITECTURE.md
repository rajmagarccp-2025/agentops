# Project Architecture

This document describes the architecture and runtime behavior. For authoritative current folder ownership, see `file-structure.md`; planned capabilities and empty scaffolding are not evidence of implementation.

## 1. Project Overview

This repository implements a cloud-agnostic Agentic SRE, FinOps and LLMOps platform. The application is structured as a multi-tier system:

- Next.js frontend for operations and governance dashboards
- FastAPI backend for API and domain services
- PostgreSQL + Redis + S3-compatible local storage for persistence and state
- RAG knowledge layer, including document ingestion, chunking, embedding, and ACL-aware retrieval
- Governance and approval boundaries for risk-controlled actions
- Observability and docker-based local development workflow

The live environment confirms the app is reachable at the expected ports:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000/api/v1/health

The backend health endpoint currently returns:

- status: ok
- service: api
- version: 0.1.0

This means the repository already has a working local baseline, but it is still a platform foundation rather than a fully hardened production deployment.

## 2. Current Architecture

```text
User Browser
    |
    v
Next.js Frontend (App Router)
    |
    +--> frontend/src/app/...
    +--> frontend/src/lib/api.ts
    +--> API base URL: http://localhost:8000/api/v1
    |
    v
FastAPI Backend
    |
    +---- /api/v1/auth
    +---- /api/v1/rag
    +---- /api/v1/incidents
    +---- /api/v1/inventory
    +---- /api/v1/finops
    +---- /api/v1/security
    +---- /api/v1/llmops
    +---- /api/v1/approvals
    +---- /api/v1/learning
    +---- /api/v1/tools
    |
    v
Authentication / Authorization
    |
    +--> JWT-based principal validation
    +--> Demo token issuance when DEMO_MODE=true
    +--> Permission checks via require_permission()
    +--> Tenant scope enforcement via verify_tenant_scope()
    |
    v
Persistence and Retrieval
    |
    +--> PostgreSQL / SQLAlchemy repositories
    +--> Redis for state/cache
    +--> RAG repository with document ACL filtering
    +--> Chunking + embeddings + retrieval + citations
    |
    v
LLM / Agent / Observability layers
    |
    +--> LangGraph-style agent contracts and MCP boundary
    +--> OpenTelemetry metrics/tracing
    +--> Approval gate for high-risk actions
    |
    v
Infrastructure and Deployment
    |
    +--> Docker Compose local stack
    +--> Helm/Argo CD deployment manifests
    +--> Terraform / cloud infrastructure templates
```

## 3. Complete Folder Structure

```text
project/
├── .env.example
├── .github/
├── .venv/
├── agents/
│   ├── definitions/
│   ├── evaluators/
│   ├── guardrails/
│   ├── memory/
│   ├── orchestration/
│   ├── policies/
│   ├── prompts/
│   ├── registry/
│   ├── schemas/
│   ├── state/
│   ├── tests/
│   ├── tools/
│   └── workflows/
├── api/
│   ├── contracts/
│   ├── examples/
│   ├── openapi/
│   ├── schemas/
│   └── versions/
├── backend/
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── requirements-dev.txt
│   ├── migrations/
│   ├── src/platform_api/
│   │   ├── api/
│   │   ├── agents/
│   │   ├── changes/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── errors.py
│   │   ├── finops/
│   │   ├── governance/
│   │   ├── identity_models.py
│   │   ├── identity_repository.py
│   │   ├── incidents/
│   │   ├── inventory/
│   │   ├── learning/
│   │   ├── llm/
│   │   ├── llmops_service/
│   │   ├── logging_config.py
│   │   ├── main.py
│   │   ├── mcp/
│   │   ├── middleware.py
│   │   ├── models.py
│   │   ├── observability.py
│   │   ├── rag_service/
│   │   ├── redis_client.py
│   │   ├── remediation/
│   │   ├── security.py
│   │   ├── security_investigation/
│   │   └── workflows/
│   └── tests/
├── config/
├── data/
├── deployment/
├── docker/
├── docs/
├── evaluation/
├── frontend/
│   ├── public/
│   ├── src/
│   ├── Dockerfile
│   ├── next.config.ts
│   ├── package.json
│   └── tsconfig.json
├── identity/
├── infrastructure/
├── llmops/
├── mlops/
├── monitoring/
├── observability/
├── operations/
├── rag/
├── scripts/
├── security/
├── tests/
├── tools/
├── README.md
├── ARCHITECTURE.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── docker-compose.yml
├── docker-compose.test.yml
├── file-structure.md
├── Makefile
├── project.md
├── LICENSE
├── SECURITY.md
└── zprompt
```

### Directory responsibilities

- backend/src/platform_api/: runtime application; this is the actual backend service code.
- frontend/src/app/: source-of-truth application pages and layouts for the Next.js UI.
- frontend/src/lib/: frontend API client and shared client-side logic.
- agents/: specifications and workflow declarations; not the runtime service itself.
- api/: API contracts and schemas; useful for contract validation and documentation.
- deployment/: canonical delivery manifests for Helm, Argo CD, Kubernetes, and deployment automation.
- infrastructure/: IaC and environment templates.
- docs/: human documentation and project architecture artifacts.
- docker/: container definitions.
- tests/: repository-level and service-level verification assets.
- data/ and rag/: knowledge and sample data structures; useful for ingestion and eval assets.

What must not be placed here:

- Generated build artifacts should not be treated as source-of-truth; `.next/` output is generated and should remain out of repo ownership.
- Runtime secrets must not be committed in repo files or `.env` files used by local developers.
- Feature implementation details should not live inside docs-only folders when there is a clear runtime owner.

## 4. File-by-File Responsibility Map

| File | Purpose | Used By | Status | Keep/Delete/Move |
|---|---|---|---|---|
| frontend/src/lib/api.ts | Frontend API client and auth token flow | Knowledge and other pages | ACTIVE | Keep |
| frontend/src/app/knowledge/page.tsx | Knowledge page UI | Browser route /knowledge | ACTIVE | Keep |
| frontend/src/app/layout.tsx | Root layout and shell | Browser | ACTIVE | Keep |
| backend/src/platform_api/main.py | FastAPI app entrypoint | uvicorn / tests | ACTIVE | Keep |
| backend/src/platform_api/config.py | Settings loader | backend runtime | ACTIVE | Keep |
| backend/src/platform_api/security.py | JWT auth, role/permission checks | API routes | ACTIVE | Keep |
| backend/src/platform_api/api/rag.py | RAG endpoints | UI + API clients | ACTIVE | Keep |
| backend/src/platform_api/rag_service/service.py | Ingestion, chunking, similarity + citations | rag API | ACTIVE | Keep |
| backend/src/platform_api/rag_service/repository.py | Document and ACL filtering logic | rag service | ACTIVE | Keep |
| backend/tests/test_rag_service.py | RAG verification tests | pytest | ACTIVE | Keep |
| backend/tests/test_auth.py | Auth verification tests | pytest | ACTIVE | Keep |
| docker-compose.yml | Local services orchestration | local dev | ACTIVE | Keep |
| .env.example | Local environment template | developers | ACTIVE | Keep |
| deployment/helm/platform | Helm deployment manifests | Kubernetes delivery | ACTIVE | Keep |
| infrastructure/terraform | IaC templates | cloud deployments | ACTIVE | Keep |
| docs/PROJECT_ARCHITECTURE.md | Project architecture source | repo users | ACTIVE | Keep |
| frontend/.next/ | Generated Next.js build output | build system only | GENERATED | Delete from source tracking |
| backend/__pycache__/ | Python bytecode cache | Python runtime | GENERATED | Delete | 

## 5. Frontend Architecture

### Runtime structure

The frontend is built with Next.js 15 and App Router. The actual source tree uses `frontend/src/app/*` rather than a `pages/` source tree. This is the authoritative UI structure.

Key frontend files:

- `frontend/src/app/layout.tsx` — root shell and global styling entry point
- `frontend/src/app/page.tsx` — landing dashboard
- `frontend/src/app/knowledge/page.tsx` — the knowledge dashboard page
- `frontend/src/app/infrastructure/page.tsx` — infrastructure view
- `frontend/src/app/incidents/page.tsx` — operational incidents
- `frontend/src/app/finops/page.tsx` — cost optimization dashboard
- `frontend/src/app/llmops/page.tsx` — LLM operations metrics
- `frontend/src/app/approvals/page.tsx` — approval queue
- `frontend/src/components/navigation.tsx` — app navigation
- `frontend/src/components/system-status.tsx` — status indicator UI
- `frontend/src/lib/api.ts` — client-side API wrapper

### API client behavior

The frontend API client defaults to `http://localhost:8000/api/v1` and can be overridden with `NEXT_PUBLIC_API_BASE_URL`.

It performs the following:

- obtains a demo JWT via POST `/api/v1/auth/demo-token`
- stores it in browser session storage
- attaches `Authorization: Bearer <token>` to protected API requests
- retries automatically when a call returns 401

The `fetchRagDocuments` and `retrieveKnowledge` calls are used by the Knowledge page.

### Knowledge page behavior

The actual Knowledge page in `frontend/src/app/knowledge/page.tsx` does the following:

1. loads documents with `fetchRagDocuments()`
2. searches with `retrieveKnowledge(query)`
3. displays documents and citations
4. renders a warning message when the backend or auth path fails

This page is functional as a UI shell, but it is not yet a complete document ingestion or knowledge management workflow.

## 6. Backend Architecture

The backend is a FastAPI application assembled in `backend/src/platform_api/main.py` and split into route modules under `backend/src/platform_api/api/`.

### Key modules

- `backend/src/platform_api/api/auth.py` — auth endpoints
- `backend/src/platform_api/api/rag.py` — document and retrieval routes
- `backend/src/platform_api/api/health.py` — health endpoints
- `backend/src/platform_api/api/inventory.py` — resource inventory
- `backend/src/platform_api/api/incidents.py` — incident routes
- `backend/src/platform_api/api/changes.py` — change intelligence routes
- `backend/src/platform_api/api/finops.py` — cost and utilization routes
- `backend/src/platform_api/api/security.py` — security investigation routes
- `backend/src/platform_api/api/llmops.py` — telemetry and evaluation routes
- `backend/src/platform_api/api/approvals.py` — approval decisions
- `backend/src/platform_api/api/tools.py` — MCP registry routes

### Core supporting modules

- `backend/src/platform_api/security.py` — JWT decode, permission enforcement
- `backend/src/platform_api/config.py` — settings and validation
- `backend/src/platform_api/database.py` — SQLAlchemy engine and session setup
- `backend/src/platform_api/observability.py` — tracing and metrics setup
- `backend/src/platform_api/rag_service/service.py` — document ingestion and ACL-aware retrieval
- `backend/src/platform_api/rag_service/repository.py` — repository backing objects

## 7. Knowledge System

### Actual flow

```text
Document ingestion request
    |
    v
POST /api/v1/rag/documents
    |
    v
DocumentCreate payload
    |
    v
chunk_text(payload.content)
    |
    v
embed_text(chunk)
    |
    v
DocumentRecord + multiple DocumentChunk records
    |
    v
repository.save_document(...)
    |
    v
Query: POST /api/v1/rag/retrieve
    |
    v
filter by tenant_id + roles + allowed_roles
    |
    v
cosine similarity score against query embedding
    |
    v
rerank and rank top citations
    |
    v
return RetrievalResult with citations + context
    |
    v
Frontend displays "Documents" and "Retrieved context"
```

### Implemented vs missing

| Stage | Status | Evidence |
|---|---|---|
| Document ingestion | IMPLEMENTED | `backend/src/platform_api/api/rag.py` and `service.py` |
| Parsing | IMPLEMENTED | `chunk_text` in `rag_service` |
| Chunking | IMPLEMENTED | `DocumentChunk` generation and per-chunk metadata |
| Embedding | IMPLEMENTED | `embed_text()` and cosine similarity final scoring |
| ACL metadata | IMPLEMENTED | `allowed_roles` on documents and filter in repository |
| Vector/index storage | PARTIALLY IMPLEMENTED | in-memory repo and SQLAlchemy-backed repo exist |
| Query filtering | IMPLEMENTED | `retrieve()` coordinates tenant/role filtering |
| Citation generation | IMPLEMENTED | `Citation` block returned from retrieval |
| Frontend display | IMPLEMENTED | `frontend/src/app/knowledge/page.tsx` |
| Ingestion UI | PARTIALLY IMPLEMENTED | button exists but no upload flow |
| File upload pipeline | MISSING | no connector or ingestion orchestration in source |
| Production vector DB tuning | MISSING | no dedicated pgvector operational strategy documented |

## 8. Authentication and Authorization

### Frontend authentication

The frontend does not maintain a static JWT. Instead, `frontend/src/lib/api.ts` calls:

- `POST /api/v1/auth/demo-token`
- stores the returned access token in browser sessionStorage
- attaches it to later requests as a Bearer token

This is a local/demo flow and is the mechanism the Knowledge page relies on.

### Backend authentication

The backend implements JWT checking in `backend/src/platform_api/security.py`:

- `get_current_principal()` reads the bearer token
- `_decode_token()` validates `iss`, `aud`, and signature
- subject and tenant_id are required
- roles and permissions are extracted from claims

### Authorization and ACL enforcement

Authorization is enforced via `require_permission(permission)` and `verify_tenant_scope()`.

The RAG ACL enforcement is implemented in `backend/src/platform_api/rag_service/repository.py`:

- documents are filtered by `tenant_id`
- documents require matching `allowed_roles`
- `platform-admin` bypasses role restrictions
- stale documents are filtered when `include_stale` is false

### Actual auth state

The repository is intentionally safe in local demo mode:

- `DEMO_MODE=true` enables the `/auth/demo-token` route
- in production, the app rejects the placeholder local JWT secret
- the default secret is rejected outside demo mode, as enforced by `Settings.validate_security_defaults()`

This means the existing auth implementation is valid for local development, not a complete production auth system.

## 9. Environment Variables

| Variable | Used By | Required | Example | Secret? |
|---|---|---|---|---|
| APP_ENV | backend settings | Yes | development | No |
| LOG_LEVEL | backend logging | Yes | INFO | No |
| DEMO_MODE | auth + demo routes | Yes | true | No |
| POSTGRES_DB | Docker/Postgres | Yes | platform | No |
| POSTGRES_USER | Docker/Postgres | Yes | platform | No |
| POSTGRES_PASSWORD | Docker/Postgres | Yes | platform | Yes |
| DATABASE_URL | backend / SQLAlchemy | Yes | postgresql+psycopg://... | Yes |
| REDIS_URL | backend / Redis | Yes | redis://redis:6379/0 | No |
| S3_ENDPOINT_URL | object storage | Yes | http://s3server:8000 | No |
| S3_ACCESS_KEY | object storage | Yes | test | Yes |
| S3_SECRET_KEY | object storage | Yes | test | Yes |
| S3_BUCKET_NAME | object storage | Yes | platform-artifacts | No |
| JWT_DEMO_SECRET | JWT generation | Yes | replace-with-a-long-random-secret | Yes |
| JWT_ALGORITHM | token validation | Yes | HS256 | No |
| JWT_ISSUER | token validation | Yes | agentic-platform | No |
| JWT_AUDIENCE | token validation | Yes | agentic-platform-api | No |
| NEXT_PUBLIC_API_BASE_URL | frontend client | Yes for production | http://localhost:8000/api/v1 | No |
| OTEL_EXPORTER_OTLP_ENDPOINT | observability | Optional | http://otel-collector:4318 | No |

### Environment issues observed

- Missing or inconsistent production variables are a real risk.
- Frontend and backend both rely on local defaults and environment assumptions.
- Secret values must be managed via `.env` for local usage and secret stores for deployment.

## 10. Docker / Local Development

The local stack is orchestrated by `docker-compose.yml`.

### Local stack

- PostgreSQL on port 5432
- Redis on port 6379
- S3-compatible server on port 9000
- Backend API on port 8000
- Frontend app on port 3000
- OpenTelemetry collector on ports 4317 and 4318

### Startup sequence

```bash
docker compose up -d postgres redis s3server
# then start API and frontend workers as needed
```

The actual runtime components are:

- `api` service
- `worker` service
- `web` service
- `postgres` service
- `redis` service
- `s3server` service
- `otel-collector` service

This is a coherent local-stack baseline, but it is not yet a full production-ready deployment workflow.

## 11. API Contract

| Endpoint | Method | Purpose | Auth | Frontend Consumer |
|---|---|---|---|---|
| /api/v1/health | GET | health check | none | frontend health/status |
| /api/v1/auth/demo-token | POST | issue demo JWT | none | frontend client |
| /api/v1/auth/me | GET | current principal | bearer | not yet used deeper |
| /api/v1/inventory/resources | GET | resource inventory | bearer | likely app dashboards |
| /api/v1/incidents | GET/POST | incident list + create | bearer | incidents UI |
| /api/v1/incidents/{id}/investigate | GET | run investigation | bearer | incident detail UI |
| /api/v1/changes | GET/POST | change events | bearer | change overview |
| /api/v1/finops/summary | GET | cost summary | bearer | dashboard |
| /api/v1/finops/recommendations | GET | recommendations | bearer | finops UI |
| /api/v1/security/investigations | POST | security investigations | bearer | security UI |
| /api/v1/llmops/telemetry | GET | LLM telemetry | bearer | llmops UI |
| /api/v1/llmops/prompts | GET/POST | prompt management | bearer | llmops UI |
| /api/v1/llmops/evaluations | GET/POST | eval results | bearer | llmops UI |
| /api/v1/rag/documents | GET/POST | list or ingest documents | bearer | Knowledge page |
| /api/v1/rag/retrieve | POST | search docs + retrieve context | bearer | Knowledge page |
| /api/v1/tools | GET | tool registry | bearer | MCP tooling pages |
| /api/v1/remediation/actions | POST | remediation actions | bearer | approvals and execution |
| /api/v1/approvals/{id}/approve | POST | approval decision | bearer | approvals UI |
| /api/v1/learning/feedback | GET/POST | learning loop | bearer | learning UI |

## 12. Current Feature Status

| Feature | Status | Evidence/File | Remaining Work |
|---|---|---|---|
| Frontend shell | COMPLETE | `frontend/src/app` and navigation components | polish and route consistency |
| Backend runtime | COMPLETE | FastAPI app starts and health endpoint returns ok | harden for production |
| Demo auth | COMPLETE in local mode | `backend/src/platform_api/security.py`, tests | production OIDC/secret management |
| JWT validation | COMPLETE | tests cover invalid tokens and tenant checks | unify with real identity provider |
| RAG ingestion | PARTIAL | `rag.py` + `service.py` | add upload pipeline and persistence tuning |
| RAG retrieval | COMPLETE | repository filtering and retrieval logic | scale to vector DB for larger datasets |
| ACL enforcement | COMPLETE | `allowed_roles` + tenant filtering | add policy-layer audit trail |
| Knowledge UI | PARTIAL | `frontend/src/app/knowledge/page.tsx` | add ingest, permission badges, error reasoning |
| Docker local stack | COMPLETE | `docker-compose.yml` | production-grade availability and secrets |
| Observability | PARTIAL | OpenTelemetry is configured | wire full exporters and alerts |
| Helm / deployment | PARTIAL | manifests exist | validate on real clusters |
| Infrastructure as code | PARTIAL | Terraform directories exist | validate cloud-specific modules |
| Production hardening | MISSING | not yet complete | full security, rate limits, backups, DR |

## 13. Current Problems

### P0 — application cannot function without local prerequisites

- Local services must be started for DB, Redis, and S3-compatible storage.
- Frontend is reachable only if API is running on the expected default URL.
- Environment variables must align between `.env.example`, Docker Compose, and runtime.

### P1 — major functionality risks

- The knowledge page shows warning states but does not provide root cause classification.
- Authentication is working in demo mode only; production identity is not yet fully implemented.
- The RAG flow is implemented in code but not yet fully validated in a production vector-storage setup.
- Some architecture docs describe larger-scale features than the current runtime actually implements.

### P2 — architecture and usability issues

- The repo mixes documentation, runtime, scaffolding, and generated content.
- There are both App Router and build-generated assets; source-of-truth is not always obvious.
- The app does not yet clearly communicate reason, cause, and permission state on failure.

### P3 — cleanup and hardening work

- Generated `.next` and Python cache directories should not be treated as source logic.
- The project requires explicit repository ownership rules and cleanup plan approval.

## 14. UI/UX Problems

The current Knowledge page is close to a working baseline, but it is still missing critical operational clarity.

The current UI should make the following obvious, but it does not yet do so consistently:

1. backend availability
2. auth validity
3. knowledge storage health
4. document count and selection
5. current user permissions
6. ingestion result state
7. retrieval result provenance
8. ACL exclusion reasons
9. failure explanation
10. recovery actions

### Recommended UI hierarchy

- Top section: backend status, auth status, docs loaded count, tenant context
- Next section: knowledge search with query and permission badge
- Then: documents table with role visibility and stale flag
- Then: retrieved context with citations, source, score, freshness marker
- Final section: error panel with failure reason and next-step guidance

This should be a minimal change, not a rewrite.

## 15. Production Readiness Checklist

| Area | Status |
|---|---|
| Frontend | [~] Partial |
| Backend | [~] Partial |
| Authentication | [x] Complete for demo flow |
| Authorization | [x] Complete for JWT + permissions |
| ACL | [x] Complete in repository layer |
| Database | [~] Partial |
| Vector database | [ ] Missing production vector strategy |
| Document ingestion | [~] Partial |
| Retrieval | [x] Complete in source code |
| Citations | [x] Complete |
| Observability | [~] Partial |
| Logging | [x] Present |
| Metrics | [~] Partial |
| Tracing | [~] Partial |
| Error handling | [~] Partial |
| Security | [~] Partial |
| Secrets | [~] Partial |
| Rate limiting | [ ] Missing |
| Retries | [~] Partial |
| Timeouts | [~] Partial |
| Testing | [~] Partial |
| CI/CD | [~] Partial |
| Docker | [x] Complete for local stack |
| Infrastructure | [~] Partial |
| Backup | [ ] Missing |
| Disaster recovery | [ ] Missing |
| Cost controls | [~] Partial |
| Audit logging | [~] Partial |

## 16. What I Should Do Next

1. Stabilize the local baseline: verify backend, database, Redis, and S3-compatible service health.
2. Validate the JWT/auth flow against real tenant and role combinations.
3. Confirm the Knowledge API path end-to-end using realistic documents and ACL rules.
4. Add explicit status visibility to the Knowledge page so failures explain whether auth, API, or storage is the issue.
5. Implement ingestion UX and document metadata management.
6. Converge on a single source-of-truth folder model and remove build artifacts from the repo view.
7. Add production-grade tests around authorization, ACL filtering, and retrieval quality.
8. Harden docker deployment with production secrets and environment validation.
9. Add metrics, tracing, and alerting at the app boundaries.
10. Review cloud IaC and deployment pipelines for production readiness.

## Phase 4 — Recommended Clean Folder Structure

```text
project/
├── app/                   # application runtime or orchestration entrypoints, if needed
├── backend/
│   ├── src/platform_api/
│   ├── tests/
│   └── migrations/
├── frontend/
│   ├── src/app/
│   ├── src/components/
│   ├── src/lib/
│   └── public/
├── docs/
├── infrastructure/
├── docker/
├── scripts/
├── tests/
├── .env.example
├── docker-compose.yml
├── README.md
└── Makefile
```

### Recommended moves

- Current: `backend/src/platform_api/api` -> Target: keep as is. The API folder is clearly runtime-owned and should remain.
- Current: `agents` -> Target: keep but treat as specification and workflow artifacts, not runtime service implementation.
- Current: `.next/` -> Target: remove from source tracking; generated output only.
- Current: `deployment/` -> Target: retain as the single deployment ownership root.
- Current: `api/` -> Target: keep as contract layer and openapi reference, not runtime logic.

### Risks

- Low: moving generated files out of source tracking.
- Medium: unifying deployment/config conventions.
- High: changing runtime ownership without validating all import paths.

## Conclusion

The repository is not a blank slate; it already contains a working local foundation for frontend, backend, auth, RAG, and Docker orchestration. The key requirement now is not a rewrite but a disciplined cleanup and stabilization effort. The repository is best treated as a platform foundation that is mostly assembled, but not yet fully hardened for production use.
