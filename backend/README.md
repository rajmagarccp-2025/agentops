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
 -> normalized embedding
 -> pgvector cosine retrieval
 -> citation context
```

Local development and unit tests use deterministic hash embeddings. Configure
`RAG_EMBEDDING_PROVIDER=vertex`, `VERTEX_PROJECT_ID`, `VERTEX_LOCATION`, and
`VERTEX_EMBEDDING_MODEL` to use Vertex AI through Application Default Credentials
(GKE Workload Identity in GCP). The active schema uses 768-dimensional vectors;
every chunk records its provider, model, version, and dimensions. Changing model
dimensions requires a schema migration and re-embedding.

Original document content is archived in Google Cloud Storage when
`RAG_DOCUMENT_STORAGE_BACKEND=gcs`; PostgreSQL remains the source of truth for
document metadata and indexed chunks. Configure `GCS_DOCUMENT_BUCKET` with an
externally provisioned bucket and use Application Default Credentials
(Workload Identity Federation on GKE); do not configure service-account key
files. The application stores original UTF-8 bytes under opaque tenant-hashed
object prefixes, verifies SHA-256 metadata on reads, and rejects content larger
than 10 MiB. A failed PostgreSQL save triggers best-effort archive cleanup and
surfaces cleanup failures. Explicit document deletion removes the GCS object as
part of the database transaction, restoring the object if the database commit
fails. There is no automatic object retention or lifecycle deletion.

Production requires the GCS backend and bucket to be configured. The bucket is
not provisioned by this repository: grant the GKE runtime service account
bucket-scoped `roles/storage.objectUser` access and confirm its Workload Identity
binding before deployment. No live bucket or IAM access is performed by tests.

Documents are scoped to the active project and either one environment or the whole
project. Environment documents are only retrievable in that environment; project
documents are shared across its environments. Existing documents without a scope
remain visible as legacy/unassigned records but are excluded from scoped retrieval
until reassigned. Retrieval also enforces `allowed_roles` unless the principal has
the platform administrator role. The `0005_rag_documents` migration establishes
PostgreSQL document and chunk persistence, and `0017_rag_workspace_scope` adds
project/environment ownership. Migration `0024_pgvector_embeddings` installs the
PostgreSQL vector extension, preserves old JSON vectors as `embedding_legacy`,
and adds the indexed 768-dimensional vector column. Existing chunks are not
retrievable until they are re-embedded. After configuring the Vertex provider and
applying the migration, run
`python -m platform_api.rag_service.reembed` as a controlled maintenance task;
it processes bounded batches and reports aggregate progress only. Do not start
production retrieval until this backfill is complete. Similarity scoring and
top-k selection run in PostgreSQL with tenant and authorized-document filters
applied before matching chunks are returned.

## Secret Manager

The GCP secret provider uses the official Secret Manager client with Application
Default Credentials (Workload Identity on GKE). Set
`GCP_SECRET_MANAGER_PROJECT_ID` to the trusted project ID. Provider requests
cannot choose another project, custom endpoint, or service-account credentials.
Secret resource names are deterministically derived from the logical secret name
and a one-way tenant hash, with scope, project, and environment included in the
logical key; version references are validated against that exact
tenant/project resource before API access.

GCP-backed create/update/rotate operations write Secret Manager versions;
restore creates a new version containing the selected historical value rather
than moving or deleting versions. Disable/re-enable affects the current GCP
version. Deleting a GCP-backed secret disables its enabled versions; it does not
permanently destroy the GCP resource or bypass configured recovery/retention.
Values are not included in provider errors or audit events. The connection test
performs a real authenticated access call to the pre-provisioned
`agentops-jwt-secret` probe and reports no payload.

The runtime service account currently has Terraform-granted access only to the
pre-provisioned platform bootstrap secrets. For application-managed secrets,
pre-provision the deterministic tenant/scope-scoped resource with labels
`managed_by=agentops` and the matching `tenant_hash`, then grant the runtime
identity `roles/secretmanager.secretAccessor`,
`roles/secretmanager.secretVersionAdder`, and
`roles/secretmanager.secretVersionManager` on that individual secret. Creating
new Secret Manager resources dynamically requires broader project-level IAM and
is intentionally not granted by this repository. Do not grant project-wide
Secret Manager administration as a shortcut.

For bootstrap settings (`DATABASE_URL`, `REDIS_URL`, OIDC, and JWT), the GCP
deploy workflow uses a short-lived deploy-time synchronization: protected GitHub
environment values seed Secret Manager only when a secret has no versions, then
Secret Manager is the source of truth and the workflow projects the selected
versions into the Kubernetes Secret consumed by pods. Pods do not fetch these
bootstrap values directly at runtime, and changing a version requires a
subsequent deployment to refresh the Kubernetes projection and restart pods.
This is not an External Secrets Operator integration or automatic rotation.
Application-managed GCP secrets, by contrast, are accessed directly through the
runtime adapter.

Secret API routes include provider configure/test, create/update, reveal,
rotation, and `POST /api/v1/secrets/{secret_id}/versions/{version_num}/restore`.
Existing tenant/scope permissions and audit logging remain required.

Runtime secret resolution uses a disposable Redis cache keyed by a one-way hash
of tenant and secret IDs. Cache entries are encrypted using the configured
application secret-encryption key, bound to the current database version ID,
limited to 64 KiB, and expire after five minutes by default. Every request still
checks tenant, scope, status, expiration, and entity assignment before using the
cache. Cache outages, timeouts, corrupt entries, and exhausted connections fall
back to the authoritative provider; cache failures are counted and logged
without secret values. Updates, rotation, restore, disable, revoke, and expiry
invalidate the corresponding cache entry.

Redis is not the source of truth for secret values, approvals, workflow status,
or audit records. The API shares an async connection pool for health/readiness
and uses a bounded synchronous pool for cache operations; both are closed at
application shutdown. Configure `REDIS_MAX_CONNECTIONS`,
`REDIS_CACHE_MAX_CONNECTIONS`, and `REDIS_CACHE_TIMEOUT_SECONDS` for the
deployment. Metrics report cache
operations/latency/errors plus Redis connected clients, memory, keyspace hits
and misses, evictions, uptime, throughput, and observed server-ID changes.
The current Memorystore Terraform resource uses private service access but does
not enable in-transit TLS; enable/verify Memorystore TLS only through a separately
reviewed infrastructure change.

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

### Durable workflow dispatch

`WORKFLOW_QUEUE_BACKEND` selects `database` (default/local) or `pubsub` (GCP).
In Pub/Sub mode, job state and request payload remain in PostgreSQL. API writes
the job and a small dispatch envelope to `workflow_outbox` in the same
transaction; the worker publishes only schema version, stable message/job IDs,
tenant ID, correlation ID, and idempotency key. No workflow payload or
credentials are published.

The worker consumes at least once and claims each job through an atomic
PostgreSQL state transition. Duplicate deliveries cannot claim an already
running or terminal job. It extends the Pub/Sub ack deadline while work runs
and acknowledges only after a durable job state is committed. Retry state,
backoff, attempt limits, and job dead-letter status are stored in PostgreSQL;
retrying a job creates the next outbox event transactionally. The worker also
polls PostgreSQL periodically as a recovery path if Pub/Sub is temporarily
unavailable. The database, not Pub/Sub ordering or exactly-once delivery, is
the authority.

Configure `WORKFLOW_PUBSUB_PROJECT_ID`, `WORKFLOW_PUBSUB_TOPIC_ID`, and
`WORKFLOW_PUBSUB_SUBSCRIPTION_ID` with resource IDs (not credentials);
Workload Identity supplies authentication. Pub/Sub delivery retries malformed
or tenant/idempotency-mismatched envelopes until the subscription routes them
to its dead-letter topic. Authorized operators should inspect the matching
durable `workflow_jobs` row before any recovery action. Do not edit or republish
a message directly. A tenant-scoped operator with `workflow:replay` can replay a
dead-lettered agent run through `POST /api/v1/agent-runs/{run_id}/replay`; the
replay and job reset are recorded in the durable audit chain. Review any
possible external side effect before replay. Terraform creates the dead-letter
topic and an operator-readable subscription; the runtime identity is not
granted access to that dead-letter subscription. Poison messages that do not
match a durable job must be investigated and acknowledged or discarded only by
an authorized Pub/Sub operator after recording the incident. Published outbox
rows for terminal jobs are purged after 30 days by default; configure
`WORKFLOW_OUTBOX_RETENTION_DAYS` to change this window.

## LLM Gateway

LLM access is available through authenticated routes:

- `GET /api/v1/llmops/models`
- `POST /api/v1/llmops/completions`

The gateway owns model routing, retry and fallback behavior, structured JSON
validation, token estimation, cost estimation, latency measurement, and telemetry
events. Provider SDKs are not imported by API or agent code. Phase 5 uses two
deterministic mock providers so local development requires no model credentials;
production uses the Google Gen AI SDK with Vertex AI and Workload Identity. Set
`LLM_PROVIDER=vertex`, `VERTEX_PROJECT_ID`, `VERTEX_LOCATION`, and the approved
`VERTEX_MODEL_*` settings. Requests are restricted to configured models, bounded
by the configured timeout, output-token limit, and concurrency limit, and sent
with safety settings. Provider failures are explicit; production settings reject
mock LLM and embedding providers. Prompts and response content are not included
in telemetry. Live synthetic Vertex and pgvector checks are marked `integration`
and skipped unless `RUN_VERTEX_INTEGRATION=true` is set with a non-production
Vertex project, PostgreSQL URL migrated through `0024_pgvector_embeddings`, and
ADC/Workload Identity access. Never put API keys in environment files.

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
