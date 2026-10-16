# Backend

FastAPI + Python backend. API routing, application services, persistence, agent
orchestration, and infrastructure adapters remain separate boundaries.

## Phase 1 foundation

- Pydantic settings loaded from environment variables and `.env`.
- SQLAlchemy 2 engine/session factory with PostgreSQL/pgvector-compatible URLs.
- Redis async client dependency with explicit lifecycle management.
- Structured JSON logging and request ID propagation.
- Typed application error envelope.
- Liveness and dependency readiness endpoints.
- Alembic environment with the initial `platform_metadata` migration.
- JWT bearer authentication with demo-only token issuance.
- Tenant-aware users, roles, permissions, and membership persistence models.
- MCP Gateway registry with typed parameters, tool discovery, risk classification,
  permission checks, dry-run behavior, and audit events.
- LangGraph runtime with typed state, supervisor routing, checkpoint retrieval,
  specialist discovery/investigation/remediation nodes, and gateway-only access.
- Discovery and Inventory Agent contracts with normalized resources, provider and
    environment metadata, accounts, regions, services, and dependencies.
- Incident Intelligence contracts with structured incident ingestion, MCP-based
    telemetry collection, deterministic timeline correlation, hypotheses,
    confidence, and LLM investigation over collected evidence.
- RAG ingestion, chunking, deterministic local embeddings, tenant and role-aware
    retrieval, reranking, context construction, and source citations.
- Change Intelligence contracts for deployment, configuration, and infrastructure
    events with tenant-scoped service filtering and incident timeline correlation.
- FinOps cost and utilization ingestion with service rollups, anomaly detection,
    idle-resource detection, rightsizing recommendations, and simple forecasting.
- Security Investigation contracts for IAM events, policy violations, suspicious
    activity, vulnerability findings, severity, confidence, and governed actions.
- LLMOps telemetry, prompt versions, evaluation results, groundedness, retrieval
    quality, tool-call correctness, latency, cost, and success metrics.
- Centralized policy and approval controls with risk decisions, expiring approval
    requests, tenant isolation, and checkpoint-backed remediation resume.
- Controlled remediation with allowlisted Kubernetes restart, scale, and rollback
    actions, dry-run support, idempotency keys, and post-action verification.
- Post-remediation verification with before/after metric deltas, recovery
    confidence, feedback capture, and tenant-scoped learning records.
- OpenTelemetry request, workflow, MCP, and LLM spans with Prometheus-compatible
    counters and optional OTLP export.
- Configurable SQLAlchemy connection pooling with pre-ping, bounded overflow,
    timeout, and connection recycling.
- Incident records use PostgreSQL-backed repositories outside `DEMO_MODE`; local
    demo mode keeps deterministic in-memory repositories for credential-free runs.
- Inventory resources and change events use the same demo/production repository
    boundary with tenant-filtered PostgreSQL queries and replacement semantics.
- FinOps cost/utilization records and security events use the same PostgreSQL
    persistence boundary outside `DEMO_MODE`, while local runs remain credential-free.
- RAG documents/chunks and LLMOps prompt/evaluation records now use PostgreSQL
    repositories outside `DEMO_MODE`, including tenant and role-aware retrieval.
- Approval requests, remediation actions, verification outcomes, and learning
    feedback now have production repository boundaries outside `DEMO_MODE`.

Local Docker Compose runs enable `DEMO_MODE` by default so visitors can explore
the read-only sample console without signing in. Set `DEMO_MODE=false` to disable
it. Production deployments must keep demo mode disabled and provide a replacement
`JWT_DEMO_SECRET`; the default local secret is rejected outside demo mode. OIDC
issuer configuration is reserved for the provider-backed verifier boundary and
is not contacted during local tests.

## MCP Gateway

Tool access is available through authenticated routes:

- `GET /api/v1/tools`
- `GET /api/v1/tools/{tool_name}`
- `POST /api/v1/tools/{tool_name}/execute`

The local registry contains deterministic inventory and Kubernetes mock tools.
Agents must depend on this registry boundary rather than cloud SDKs, Kubernetes
clients, shell commands, or Terraform. `HIGH_RISK` and `CRITICAL` tools return
`approval_required` and do not invoke their handler until the approval service is
implemented in a later phase.

## Discovery and Inventory

Discovery runs normalize mock cloud results into tenant-scoped inventory records.
Resources are available through:

- `GET /api/v1/inventory/resources`

The current local adapter emits AWS-shaped demo resources, account and region
metadata, service names, and a service dependency edge. The normalized schema is
provider-neutral and the `resources` migration provides the persistence boundary
for the database-backed repository.

## Incident Intelligence

Incident routes:

- `POST /api/v1/incidents`
- `GET /api/v1/incidents/{incident_id}`
- `POST /api/v1/incidents/{incident_id}/investigate`

Investigation flow:

```text
Incident
 -> MCP observability signals
 -> deployment and change correlation
 -> evidence timeline
 -> hypotheses and confidence
 -> LLM Gateway investigation
```

The LLM receives collected evidence and is not used as the source of telemetry or
timeline facts. Incident records are tenant-isolated, and the `0004_incidents`
migration establishes the database persistence boundary.

## Controlled Remediation

Remediation routes:

- `POST /api/v1/remediation/actions`
- `POST /api/v1/remediation/actions/{record_id}/verify`

Only the allowlisted Kubernetes actions are accepted. High-risk and critical
actions remain approval-gated, while dry runs can be verified without changing
infrastructure. Idempotency keys prevent duplicate execution requests. The
`0011_remediation_actions` migration establishes the persistence boundary.

## Verification and Learning

Verification and feedback routes:

- `POST /api/v1/learning/remediation/{record_id}/verify`
- `POST /api/v1/learning/feedback`
- `GET /api/v1/learning/feedback`

Verification compares baseline and post-action latency/error metrics, reports
recovery and confidence, and records the result for future evaluation. Operators
can attach usefulness feedback and labels to remediation outcomes. The
`0012_verification_learning` migration establishes the persistence boundary.

## Observability

Metrics are available at:

- `GET /api/v1/metrics`

Instrumentation covers:

- HTTP request spans and request/response counters
- LangGraph workflow spans and run counters
- MCP tool spans and execution counters
- LLM provider spans and success/failure counters

Set `OTEL_EXPORTER_OTLP_ENDPOINT` to enable OTLP gRPC export. Without that
setting, local spans remain no-op/export-free while counters remain available for
local validation.

## Change Intelligence

Change routes:

- `POST /api/v1/changes`
- `GET /api/v1/changes/{service}`

Change events include service, environment, type, timestamp, source, actor, and
structured details. Incident correlation consumes recorded events when available,
then falls back to deterministic demo deployment and configuration events for the
local scenario. The `0006_change_events` migration establishes the persistence
boundary.

## FinOps

FinOps routes:

- `POST /api/v1/finops/costs`
- `POST /api/v1/finops/utilization`
- `GET /api/v1/finops/recommendations`
- `GET /api/v1/finops/summary`

Recommendations are derived from tenant-scoped cost and utilization records:

```text
Cost + utilization
 -> service rollups
 -> anomaly and idle-resource detection
 -> rightsizing analysis
 -> savings estimate and confidence
 -> approval-required recommendation
```

No FinOps recommendation automatically changes infrastructure. The `0007_finops`
migration establishes cost and utilization persistence; provider billing adapters
can populate the same contracts later.

## Security Investigation

Security routes:

- `POST /api/v1/security/events`
- `POST /api/v1/security/investigations`

The investigation path collects read-only security events through MCP, classifies
evidence by event type and severity, and emits confidence-scored findings with
approval-required recommendations. The `0008_security_events` migration establishes
the persistence boundary. No security remediation is executed automatically.

## LLMOps

LLMOps routes:

- `GET /api/v1/llmops/telemetry`
- `POST /api/v1/llmops/prompts`
- `GET /api/v1/llmops/prompts`
- `POST /api/v1/llmops/evaluations`
- `GET /api/v1/llmops/evaluations`

The evaluation service records correctness, groundedness, retrieval quality,
tool-call correctness, latency, estimated cost, and success. Telemetry reads are
tenant-filtered over gateway events. Prompt versions and evaluation results are
persisted behind the `0009_llmops` migration boundary.

## Policy and Approval

Approval routes:

- `GET /api/v1/approvals`
- `GET /api/v1/approvals/{request_id}`
- `POST /api/v1/approvals/{request_id}/approve`
- `POST /api/v1/approvals/{request_id}/reject`

High-risk and critical MCP actions create an expiring approval request. Approval
execution is the only path that enables the controlled MCP `approved` execution
flag. Approved remediation updates the LangGraph checkpoint and exposes the final
execution state through the existing agent-run endpoint. The `0010_approvals`
migration establishes the database persistence boundary.

## RAG Service

RAG routes:

- `POST /api/v1/rag/documents`
- `GET /api/v1/rag/documents`
- `PATCH /api/v1/rag/documents/{document_id}/scope`
- `DELETE /api/v1/rag/documents/{document_id}`
- `POST /api/v1/rag/retrieve`

The local pipeline is:

```text
Document
 -> chunking
 -> metadata and ACLs
 -> deterministic embedding
 -> cosine retrieval
 -> citation context
```

Documents are scoped to the active project and either one environment or the whole
project. Environment documents are only retrievable in that environment; project
documents are shared across its environments. Existing documents without a scope
remain visible as legacy/unassigned records but are excluded from scoped retrieval
until reassigned. Retrieval also enforces `allowed_roles` unless the principal has
the platform administrator role. The `0005_rag_documents` migration establishes
PostgreSQL document and chunk persistence, and `0017_rag_workspace_scope` adds
project/environment ownership. The current local repository uses JSON embeddings
until the pgvector-backed adapter is introduced.

## Cloud Integrations

Cloud integration identity references are managed through:

- `GET /api/v1/cloud-integrations/providers`
- `GET /api/v1/cloud-integrations`
- `POST /api/v1/cloud-integrations`
- `DELETE /api/v1/cloud-integrations/{integration_id}`

Records are tenant, project, and environment scoped. They contain an account
identifier and an external identity or secret-manager reference, never provider
credentials. These references are deliberately reported as `unverified`: the API
does not authenticate with cloud providers, validate credentials, or discover
resources. `0018_cloud_integrations` adds persistence. Production deletions require
the `X-Confirm-Production-Environment` header to exactly match the active
environment slug; environment and RAG-document deletion use the same safeguard.

## Observability

`GET /api/v1/observability/metrics` returns an authenticated, whitelisted snapshot
of cumulative process-wide counters. It is not historical or environment-specific.
LLM telemetry is tenant-filtered but currently in memory, and agent-run history is
also in memory and filtered by the active project/environment. Logs and traces are
not queryable until an external observability query backend is configured.

## Agent Runtime

Agent runs are available through:

- `POST /api/v1/agent-runs`
- `GET /api/v1/agent-runs`
- `GET /api/v1/agent-runs/{run_id}`

The supervisor routes discovery, investigation, and remediation requests to
focused nodes. Nodes do not call provider or infrastructure APIs directly; they
use the MCP and LLM Gateway boundaries. The local runtime uses LangGraph's
in-memory checkpoint saver. Remediation pauses with `approval_required` when the
MCP risk policy blocks a high-risk operation.
Run records carry the project/environment active when the run was started; list
and detail responses include this workspace scope.

## LLM Gateway

LLM access is available through authenticated routes:

- `GET /api/v1/llmops/models`
- `POST /api/v1/llmops/completions`

The gateway owns model routing, retry and fallback behavior, structured JSON
validation, token estimation, cost estimation, latency measurement, and telemetry
events. Provider SDKs are not imported by API or agent code. Phase 5 uses two
deterministic mock providers so local development requires no model credentials;
OpenAI, Azure OpenAI, Bedrock, Vertex, and self-hosted adapters attach behind the
same provider protocol in later implementation phases.

Run from the repository root:

```text
make migrate
```

PostgreSQL must be running before applying migrations. Domain-specific tables
are introduced incrementally with their owning feature phases.

## Database Operations

Database settings are environment-driven through `DATABASE_URL` and the
`DATABASE_POOL_*` variables. Apply the migration chain before starting API
workers:

```text
make migrate
```

Readiness checks execute `SELECT 1` against PostgreSQL and `PING` against Redis.
The `/api/v1/health/ready` response is degraded when either dependency is
unavailable, allowing Kubernetes to remove unhealthy pods from service.

## Demo mode and authorization

Demo mode is opt-in (`DEMO_MODE=true`) and is rejected in production. Demo
sessions carry a signed read-only claim; the API rejects state-changing requests
even when a client bypasses the disabled controls. Read-only knowledge retrieval
and workspace-context switching remain available. The public demo-token endpoint
issues a read-only `READ` principal and is unavailable when demo mode is disabled.
Project and environment administrators receive scoped permission sets rather than
organization-wide administrator privileges. SSO account linking requires the
authenticated principal's verified email to match the requested identity.
