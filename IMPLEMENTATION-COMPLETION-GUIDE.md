# End-to-End Implementation Completion Guide

This runbook translates the repository audit into implementation work, in a
safe dependency order. It is intended to be followed against the GCP profile
currently described in `infrastructure/terraform/gcp` and
`.github/workflows/deploy-gcp.yml`.

> **Important:** a Terraform resource, a passing unit test, or a successful image
> pull does not prove that the production service is deployed, connected, secure,
> observable, or healthy. Do not mark an item complete until its acceptance
> checks below pass in the intended GCP project and GKE cluster.

## Outstanding items

The following is the initial checklist of work remaining or requiring live
verification. “Partial” means some foundation/configuration exists, but the
end-to-end capability is not yet demonstrated.

1. [ ] **Cloud DNS, Cloud Armor, and global external load balancer — Partial.**
   Opt-in Terraform and GKE Gateway resources now exist, including DNS
   authorization and a managed certificate. They are disabled by default and
   have not been applied or tested against an owned domain.
2. [ ] **Kong Gateway and AI Gateway — Partial.** The GCP Helm/workflow path now
   deploys a private Kong OSS API edge, but live rollout is unverified and
   Kong AI Gateway routing/policies are intentionally not configured.
3. [ ] **Cloud Logging, Cloud Monitoring, Cloud SQL/PostgreSQL, and BigQuery —
   Partial.** An OTLP Collector and Prometheus scrape/export path are
   configured. Cloud SQL/PostgreSQL exists in Terraform; BigQuery integration,
   dashboards, alerting, and verified telemetry delivery remain.
4. [ ] **OPA/Rego policy checks — Partial.** Versioned Rego policy/tests,
   fail-closed API integration, and a private OPA chart deployment are present;
   live GKE and durable audit acceptance remain.
5. [ ] **Project completion — Not yet demonstrated.** The project scope claims
   phases complete, but live deployment and several production integrations
   remain unverified or explicitly absent.
6. [ ] **Codebase understanding — Audit performed; operational walkthrough
   remains.** Use the architecture map in this guide and verify each service
   against deployed resources.
7. [ ] **Cloud Storage state and PAC documents — Partial.** OpenTofu state,
   artifact, and RAG document storage have separate roles. The application
   archives original documents in an externally provisioned GCS bucket while
   PostgreSQL stores metadata/chunks. Bucket ownership, IAM, live access, and
   policy-as-code-specific ingestion remain unverified.
8. [ ] **Redis memory/cache — Partial.** An encrypted, tenant-scoped,
   version-bound Redis cache and Memorystore configuration exist. Production
   connectivity, availability, and transport-security acceptance remain.
9. [ ] **Vertex AI models and embeddings — Implemented in source; live proof
   pending.** Vertex providers, routing, embeddings, and pgvector persistence
   are configured; production credentials, quotas, live calls, and migration
   acceptance remain.
10. [ ] **GCP Secret Manager — Implemented in source; live proof pending.**
    The application uses the official GCP client and Workload Identity; actual
    resource access, rotation, and IAM acceptance remain.
11. [ ] **Internal MCP Gateway — Partial.** Registry, validation, authorization,
    idempotency, and audit scaffolding exist; default tool handlers are mocked
    and are not live provider integrations.
12. [ ] **LLM Gateway — Partial.** Tenant controls, budgets, bounded retries,
    and Vertex routing are implemented. Provider health checks and real
    production calls remain unverified.
13. [ ] **Logging, metrics, traces, and observability — Partial.** Structured
    stdout logging, OTLP traces, and Collector-based metrics export are
    configured. Dashboards, alerts, on-call routing, and live delivery remain.
14. [ ] **Pub/Sub — Partial.** Transactional outbox publishing, Pub/Sub
    consumption, retry/DLQ handling, and replay are implemented. Live GCP
    delivery and failure recovery remain unverified.

## How to use this runbook

- Perform the steps in order. Items 1–3 establish the deployment foundation;
  steps 4–12 implement the runtime integrations; steps 13–14 prove deployment
  health and completion.
- GCP commands below are Bash commands for **Google Cloud Shell** or a trusted
  CI runner. They assume `gcloud`, `kubectl`, `helm`, and `tofu` are installed.
  Do not paste credentials into source files, command history, tickets, or chat.
- Replace every `<...>` placeholder with an approved value. Use the existing
  `project-cks-aug2026` project only if it is still the approved target.
- Production provisioning can create billable resources. Review each plan,
  permissions change, DNS cutover, and rollout before applying it.
- Keep Terraform/OpenTofu state in the configured remote GCS backend. Do not
  use `-backend=false` for production plans/applies, delete state, or hand-edit
  state to work around drift. CI may use backendless initialization only for
  static validation; it must not plan or mutate resources.
- Add or update tests as part of each code change. The final gate is the
  repository CI plus live integration checks, not just commands in this guide.

## Repository map

| Area | Location | Role |
|---|---|---|
| Backend API and services | `backend/src/platform_api` | FastAPI routes, LLM/RAG, MCP, secrets, queue, governance, telemetry |
| Backend tests | `backend/tests` | Unit, integration, security and end-to-end scenarios |
| GCP infrastructure | `infrastructure/terraform/gcp` | GKE Autopilot, VPC, Cloud SQL, Memorystore, GCS, Pub/Sub, IAM, secrets |
| GCP deployment | `.github/workflows/deploy-gcp.yml` | OIDC auth, OpenTofu apply, image build, opt-in Helm rollout |
| GKE smoke test | `.github/workflows/gke-smoke-test.yml` | Cluster scheduling and image-pull check only |
| Helm | `deployment/helm/platform` | API, worker, frontend, policies and GCP values |
| Kong config | `deployment/kong/kong.yml` | Existing API proxy configuration; currently local/dev-oriented |
| RAG document types | `backend/src/platform_api/rag_service/schemas.py` | `runbook`, `postmortem`, `policy`, `architecture`, `ticket`, `cloud_documentation` |
| Project design | `project-scope.md`, `project.md` | Target architecture and scope; not proof of deployed state |

---

## Sequence 1 — Confirm target, baseline, and safe deployment access

### Implement

1. Confirm the production GCP project, region, DNS zone/domain, public endpoint
   ownership, approved gateway, data-retention requirements, and whether PAC
   means policy-as-code documents.
2. Keep separate identities for GitHub deployment and the GKE workload. Use
   Workload Identity Federation; do not create or check in service-account key
   files.
3. Confirm required GitHub `prod` environment secrets described in
   `infrastructure/terraform/gcp/README.md` are configured in GitHub, not in
   `.env` or source control. Add a separate DNS zone name/domain and any
   third-party provider credentials only through approved secret storage.
4. Review the current Terraform IAM scopes. Replace broad bootstrap roles with
   least-privilege custom roles after validating required operations; never
   grant project `Owner` as a shortcut.
5. Confirm the existing state bucket is the intended production state and
   restrict access to the state bucket. State may contain sensitive values.

### Commands (Cloud Shell)

```bash
export PROJECT_ID="project-cks-aug2026"  # Replace if the approved project differs.
export REGION="us-central1"
export CLUSTER="agentops-platform-prod"
export NAMESPACE="prod"
gcloud config set project "$PROJECT_ID"
gcloud auth list
gcloud projects describe "$PROJECT_ID" --format='value(projectId,projectNumber)'
gcloud container clusters describe "$CLUSTER" \
  --region "$REGION" --project "$PROJECT_ID" \
  --format='value(name,status,location)'
gcloud storage buckets describe "gs://${PROJECT_ID}-agentops-tofu-state"
```

If the state bucket name or project does not match the backend configured in
`infrastructure/terraform/gcp/versions.tf`, stop and resolve ownership/state
before running any plan or apply. Do not silently point production Terraform at
a new empty state.

### Acceptance

- Target project, DNS owner, domain, and environment are approved.
- GitHub Actions authenticates with OIDC; runtime uses its distinct GKE
  Workload Identity service account.
- The remote state bucket exists, is versioned/private, and is the state used
  by the checked-out Terraform root.
- No production credentials are tracked by Git:

```bash
git status --short
git grep -n -I -E 'AIza[0-9A-Za-z_-]{20,}|-----BEGIN (RSA |EC )?PRIVATE KEY-----' -- ':!*.lock'
```

Investigate matches manually; do not treat test fixtures or public keys as
credentials without checking context.

---

## Sequence 2 — Provision and verify the GCP foundation

### Implement

1. Review `infrastructure/terraform/gcp/main.tf`. It already defines the
   Autopilot cluster, VPC/private service networking, Cloud SQL PostgreSQL 16,
   Redis, GCS artifact bucket, Pub/Sub resources, Secret Manager containers,
   KMS, and runtime IAM bindings.
2. Add missing APIs/resources/IAM only when required by later steps. Keep
   resources in this GCP root, use variables for project/domain/environment,
   enable deletion protection for production data resources, and avoid
   project-wide `Editor` roles.
3. Ensure the Cloud SQL database is provisioned with the required PostgreSQL
   extensions through a repeatable migration/bootstrap step. Confirm the
   selected Cloud SQL edition supports the chosen extension before rollout.
4. Review production sizing, backups/PITR, maintenance windows, HA, retention,
   and recovery objectives. A successful `tofu apply` is not a recovery test.

### Commands (Cloud Shell; run from repository root)

```bash
cd infrastructure/terraform/gcp
tofu init
tofu fmt -check
tofu validate
# Optional local plan only: prefer the protected GitHub environment secret.
# This prompts without echo; do not use a literal password on the command line.
read -rsp "Cloud SQL database password: " TF_VAR_database_password; echo
export TF_VAR_database_password
tofu plan -input=false -var="project_id=$PROJECT_ID" \
  -var="project_name=agentops-platform" \
  -var="environment=prod" \
  -var="region=$REGION" \
  -var="namespace=$NAMESPACE" \
  -var="service_account_name=agentops-platform-sa-gcp" \
  -out=tfplan
tofu show tfplan
```

Alternatively, supply `database_password` through the approved CI secret
mechanism (the workflow uses `TF_VAR_database_password` from
`TF_DATABASE_PASSWORD`). Do not put it in a tracked `.tfvars` file or use a
literal password in shell history. Only after a human has reviewed the plan:

```bash
tofu apply -input=false tfplan
unset TF_VAR_database_password
tofu output
gcloud container clusters get-credentials "$CLUSTER" \
  --region "$REGION" --project "$PROJECT_ID"
kubectl get nodes
kubectl get namespaces
```

### Acceptance

- `tofu validate` and the reviewed production plan pass with no unintended
  replacement/deletion.
- `tofu state list` contains expected production resources and state remains
  remote.
- GKE cluster is `RUNNING`; private Cloud SQL/Redis endpoints are not exposed
  publicly; backups and deletion protection are confirmed.
- `kubectl get nodes` and GKE API access succeed for the intended operator.

---

## Sequence 3 — Cloud SQL/PostgreSQL and BigQuery integration

### Implement

1. Keep PostgreSQL/Cloud SQL as the transactional system of record. Ensure
   production `DATABASE_URL` is set by the deployment secret flow and uses
   private networking and TLS as configured.
2. Add a migration or controlled initialization job for extensions used by the
   app, notably `vector` if pgvector is selected. Make it repeatable and verify
   extension availability against the provisioned Cloud SQL engine.
3. Verify tenant-scoped repository queries and authorization tests on PostgreSQL
   (not only SQLite/in-memory). Add a Cloud SQL integration test environment
   using ephemeral test data.
4. **BigQuery is not currently provisioned or integrated.** First identify a
   business use case (for example, aggregated analytics/audit reporting). If
   required, add a separate dataset/table schema, retention policy, and
   dedicated writer/reader service account permissions. Export only minimized,
   approved data; do not copy credentials, raw prompts, or sensitive tenant
   data by default. If BigQuery is not needed, record “not in scope” rather than
   claiming it is integrated.
5. Implement a typed BigQuery adapter using the official Google Cloud client,
   with Workload Identity auth, parameterized queries, timeouts, retries,
   tenant filters, and explicit error reporting.

### Commands

```bash
# Check live Cloud SQL instance and database connectivity from GKE.
gcloud sql instances describe "agentops-platform-prod-db" \
  --project "$PROJECT_ID" \
  --format='value(state,region,databaseVersion,settings.ipConfiguration.ipv4Enabled)'
kubectl -n "$NAMESPACE" get deploy,pods
kubectl -n "$NAMESPACE" exec deploy/platform-api -- \
  python -c 'import os; print("DATABASE_URL configured:", bool(os.getenv("DATABASE_URL")))'

# From a configured PostgreSQL client/network path, verify extension and schema.
psql "$DATABASE_URL" -c 'SELECT version();'
psql "$DATABASE_URL" -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

If database access is via the Cloud SQL Auth Proxy or connector, use the
approved private connection path rather than opening a public IP. Never echo
`DATABASE_URL` to CI logs.

For BigQuery, after implementing Terraform resources and the adapter:

```bash
gcloud bigquery datasets describe "${PROJECT_ID}:<DATASET_ID>"
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) AS rows FROM `<PROJECT_ID>.<DATASET_ID>.<TABLE_ID>`'
```

Run the query as the application identity or a least-privileged test identity,
not only as a project administrator.

### Acceptance

- API readiness reports PostgreSQL healthy in GKE.
- Migrations pass on the target PostgreSQL version; expected extension is
  present; restore from backup has been exercised in a non-production test.
- Tenant-boundary tests pass against PostgreSQL.
- If BigQuery is in scope, an end-to-end test writes and reads an approved
  synthetic record using workload identity and rejects cross-tenant access.

---

## Sequence 4 — Cloud Storage for state and RAG documents

### Implement

1. Preserve the separation already documented:
   - OpenTofu state bucket: backend state only, highly restricted access.
   - Application artifact bucket: artifacts, not Terraform state.
   - Add a separate private documents bucket if RAG documents need durable
     object storage. Do not mix user documents with the state bucket.
2. Add a GCS document-store adapter behind a storage interface. Use the
   workload identity; avoid service-account JSON keys. Implement object
   metadata, checksum, versioning, retention/lifecycle, encryption, safe
   download limits, and tenant-scoped object paths/metadata.
3. Store document metadata/ACL and indexing state in PostgreSQL; store content
   in GCS only if required by the product. Verify authorization before
   returning object bytes or indexing content.
4. For this runbook, **PAC means policy-as-code files** such as `.rego` policies
   and policy bundles. RAG `DocumentType.POLICY` can categorize their
   explanatory/document representation, but it does not execute policies.
   Store policy bundles as versioned, integrity-checked artifacts separate
   from ordinary text documents. If “PAC” means another document type, update
   this design before implementation.
5. Extend RAG ingestion with explicit source provenance, version, tenant,
   project/environment scope, allowed roles, deletion propagation, and
   re-indexing behavior.

### Commands

```bash
gcloud storage buckets describe "gs://${PROJECT_ID}-agentops-artifacts"
gcloud storage buckets describe "gs://<PRIVATE_DOCUMENT_BUCKET>"
gcloud storage buckets get-iam-policy "gs://<PRIVATE_DOCUMENT_BUCKET>"
```

For implementation dependencies, add the approved Google Cloud Storage client
to `backend/pyproject.toml`, then install through the project workflow:

```bash
python -m pip install -e "backend[dev]"
```

Add focused tests for upload, download, missing object, checksum mismatch,
tenant/ACL denial, object deletion, and GCS outage. Use an isolated test bucket
and synthetic documents; never run destructive tests against production data.

### Acceptance

- State bucket and document bucket are distinct, private, versioned as
  appropriate, and have least-privileged IAM.
- Application reads/writes a synthetic document through Workload Identity;
  unauthorized tenants cannot fetch, list, or index it.
- Document deletion removes or tombstones the object and its chunks/embeddings
  according to the agreed retention policy.
- PAC bundle storage is versioned and verified; it is not misrepresented as
  already being supported by the generic `policy` RAG type.

---

## Sequence 5 — Complete Secret Manager runtime integration

### Implement

1. Replace the synthetic GCP behavior in
   `backend/src/platform_api/secrets/providers/adapters.py` with the official
   Secret Manager client. Implement real create, add-version/update, access,
   disable/destroy (as approved), metadata, and connection-test operations.
2. Parse/validate allowed secret resource names. Do not accept arbitrary
   project IDs or resource paths from an untrusted request. Scope access by
   tenant/secret ownership and server-side authorization.
3. Use Workload Identity and Secret Manager IAM; never create a service-account
   key. Keep secret payloads out of logs, traces, exceptions, API responses,
   telemetry, and audit records.
4. Resolve the current deployment duplication: `.github/workflows/deploy-gcp.yml`
   publishes secrets to Secret Manager and also creates a Kubernetes Secret.
   Choose one production source-of-truth. Prefer External Secrets Operator with
   a SecretStore/ClusterSecretStore backed by GCP Secret Manager, or justify and
   document a short-lived deploy-time sync. Do not claim Secret Manager
   runtime integration while pods only read Kubernetes secrets written by CI.
5. Add rotation/version rollback behavior and verify that application reload
   or rollout uses the intended version.

### Commands

```bash
# Verify secret containers exist without printing secret contents.
gcloud secrets list --project "$PROJECT_ID" \
  --format='table(name,replication.automatic)'
gcloud secrets get-iam-policy agentops-database-url --project "$PROJECT_ID"

# Add a synthetic test secret through an approved protected prompt/secret file.
# Do not put a real secret literal into this command or commit a temp file.
printf '%s' "$SYNTHETIC_TEST_VALUE" |
  gcloud secrets versions add <TEST_SECRET_ID> \
    --project "$PROJECT_ID" --data-file=-
gcloud secrets versions list <TEST_SECRET_ID> --project "$PROJECT_ID"
```

Use the application service identity for integration tests. Do not print or
`gcloud secrets versions access` real production values in logs.

### Acceptance

- Live connection check makes an authenticated Secret Manager API call (not a
  synthetic success response).
- Create/read/update/rotate/disable behavior is tested with a dedicated
  synthetic secret and least privilege.
- Secret values are redacted; unauthorized identities and tenants are denied.
- GKE pod consumes the selected secret version through the approved runtime
  mechanism; rotation is exercised without exposing values.

---

## Sequence 6 — Implement Redis as an explicit cache/memory layer

### Implement

1. Inventory required cache use cases. Keep approvals, workflow status, audit
   records, and other durable business state in PostgreSQL; Redis must not be
   their sole copy.
2. Add explicit repository/cache functions with tenant-safe keys, TTLs,
   serialization versioning, maximum value sizes, and invalidation. Do not use
   user-controlled raw keys or cache authorization decisions without invalidation.
3. Define outage behavior per use case: bypass disposable cache only when safe;
   apply bounded DB protection/rate limits; fail closed for security-sensitive
   limits or state that must be durable.
4. Add latency, hit/miss, evictions, errors, connections, memory, and failover
   metrics without high-cardinality tenant labels. Configure Redis TLS/auth
   according to Memorystore capabilities and topology.

### Commands

```bash
gcloud redis instances describe agentops-platform-prod-redis \
  --region "$REGION" --project "$PROJECT_ID" \
  --format='value(state,tier,memorySizeGb,host,connectMode,authorizedNetwork)'
kubectl -n "$NAMESPACE" port-forward svc/platform-api 8000:8000
```

Keep the port-forward running in one terminal. From a second authorized
terminal, run the health check and confirm the response reports both `database`
and `redis` as `ok`. Never print the Redis URL in a command or log.

```bash
curl --fail --show-error http://127.0.0.1:8000/api/v1/health/ready
```

### Acceptance

- Cache data is disposable/reconstructable; durable writes remain in PostgreSQL.
- Tenant isolation tests prove cache-key separation and no cross-tenant reuse.
- TTL, invalidation, Redis outage, connection exhaustion, and failover tests pass.
- GKE readiness and production metrics report actual Redis reachability and
  cache behavior.

---

## Sequence 7 — Connect Pub/Sub to durable workflow execution

### Implement

1. Define a queue interface shared by the existing database queue and a GCP
   Pub/Sub implementation. Keep the database queue for local/non-GCP profiles;
   select Pub/Sub for the GCP profile only after parity tests pass.
2. Implement publisher and subscriber clients using workload identity and
   least-privilege topic/subscription IAM. Include schema version, message ID,
   tenant ID, correlation ID, and idempotency key; never put credentials or
   unrestricted sensitive payloads in messages.
3. Make message handling idempotent and acknowledge only after durable job
   state/action receipts are committed. Define lease/visibility, retry,
   backoff, dead-letter, replay, and poison-message procedures.
4. Reconcile ordering and exactly-once assumptions: design for duplicate
   delivery. Preserve PostgreSQL as the authoritative workflow/action record.
5. Add an outbox or equivalent transactional publishing pattern if a database
   commit and message publish must be consistent.

### Commands

```bash
gcloud pubsub topics describe agentops-platform-prod-events --project "$PROJECT_ID"
gcloud pubsub subscriptions describe agentops-platform-prod-events \
  --project "$PROJECT_ID"
gcloud pubsub topics describe agentops-platform-prod-events-dlq \
  --project "$PROJECT_ID"
```

After implementing an integration test using a dedicated non-production topic:

```bash
pytest backend/tests -q -k 'pubsub or workflow_queue'
```

Test duplicate delivery, subscriber restart, transient API failure, dead-letter
routing, retry limit, tenant mismatch, idempotency collision, and replay.

### Acceptance

- GCP worker actually receives and processes a synthetic Pub/Sub job and stores
  durable status/action receipt in PostgreSQL.
- Duplicate delivery creates no duplicate action.
- Failed/poison messages reach the configured DLQ and can be diagnosed/replayed
  through a documented, authorized procedure.
- Switching between PostgreSQL and Pub/Sub backends is configuration-driven
  and does not change application business semantics.

---

## Sequence 8 — Replace mock Vertex AI models and embeddings

### Implement

1. Add a real Vertex AI provider for the LLM gateway, using the supported
   Google Gen AI/Vertex SDK and GKE Workload Identity. Use configured model IDs,
   location, project, timeouts, bounded retries, quotas, safety settings, and
   model-use policy. Never silently fall back to a mock in production.
2. Add a real Vertex embedding provider behind an embedding interface. Store
   provider/model/version/dimensions with embedding records; plan a re-embedding
   migration when model or dimensions change.
3. Replace hash vectors as the production provider while retaining a
   deterministic fake provider for unit tests. Validate embedding vector size
   and normalize consistently.
4. Before using pgvector, provision/enable the extension and change the
   embedding column/index/retrieval implementation from JSON + in-process
   cosine scoring to pgvector operators/indexes. Ensure tenant/document ACL
   filters are applied in the database query before returning chunks.
5. Add provider outages, quota exhaustion, malformed response, timeout,
   dimension mismatch, and no-data tests. Treat retrieved documents as untrusted
   input and preserve citations/ACL enforcement.

### Commands

```bash
gcloud services list --enabled --project "$PROJECT_ID" \
  --filter='config.name:aiplatform.googleapis.com'
gcloud projects get-iam-policy "$PROJECT_ID" \
  --flatten='bindings[].members' \
  --filter='bindings.role:roles/aiplatform.user'
```

After deploying the adapter, run its tests with a non-production model/project
and synthetic prompts. Verify the deployed pod identity; do not test by
embedding API keys in environment files.

### Acceptance

- A live Vertex AI request from the GKE workload identity succeeds; logs show
  model/latency/usage metadata but no prompt/secret leakage.
- A live embedding request returns the expected dimension and is persisted and
  retrieved with tenant/project/environment ACL filters.
- All provider failure modes are visible and bounded; production cannot silently
  return mock content.
- Unit tests continue using deterministic fakes; integration tests are clearly
  marked and require explicit GCP configuration.

---

## Sequence 9 — Make the LLM Gateway production-ready

### Implement

1. Replace `default_gateway()` mock routes in
   `backend/src/platform_api/llm/gateway.py` with configuration-selected
   production providers. Keep mock providers only in tests/demo mode.
2. Define model aliases, approved model list, provider/model allowlists,
   per-tenant budgets/quotas, maximum input/output tokens, request timeout,
   retries, fallback, and redaction policy. Validate caller permissions and
   tenant identity before sending data to a provider. Admission currently uses a
   conservative UTF-8 byte upper-bound estimate; settle daily budgets against
   provider-reported usage. Report calculated costs as estimates, not provider
   invoices.
3. Make retries bounded and retry only retryable errors. Include provider,
   model, and fallback state in telemetry; never log raw prompts or responses
   by default.
4. Add contract tests for token/cost calculations, rate limits, tenant
   isolation, provider failover, timeout and structured-output validation.
5. Decide the division of responsibility: the platform LLM Gateway owns
   business policy, tenant budgets, audit, and provider-independent API;
   Kong AI Gateway (next sequence) may own edge routing/traffic controls.
   Avoid two unsynchronized policy/routing implementations.

### Commands

```bash
pytest backend/tests -q -k 'llm_gateway or llmops'
ruff check backend/src backend/tests
```

Run a live-provider test only with a non-production tenant and synthetic input.
Check the provider's data processing/retention terms before sending production
data.

### Acceptance

- Production configuration chooses only approved, real provider adapters;
  demo/test mock mode is explicit and rejected in production.
- Tenant budgets, permissions, model allowlists, fallback, and data-redaction
  tests pass.
- Provider health checks perform real non-invasive checks or accurately report
  “not tested”; “configured” must not be presented as healthy.

---

## Sequence 10 — Deploy Kong Gateway and configure AI Gateway

**Selected scope:** Kong Gateway OSS is deployed as a private edge. The API
remains authoritative for OIDC validation, authorization, tenant scope, and LLM
governance. Kong AI Gateway is not enabled; OSS edge rate limits are local to
each replica and are not a replacement for the platform's tenant quotas.
Configure trusted proxy CIDRs before relying on client-IP limits behind a
public load balancer.

### Implement

1. Kong Gateway OSS is selected for API-edge routing only. No AI Gateway
   plugins or Enterprise license are assumed. The repository's
   `deployment/kong/kong.yml` remains Docker Compose-only: it uses local
   development identity settings and must not be used in production.
2. Deploy Kong using a supported GKE deployment method (Helm/operator) with
   Admin API private, database/declarative config secured, TLS enforced,
   readiness/liveness probes, resource requests/limits, and network policies.
3. Configure private routes to the API and edge rate/request-size limits. This
   deployment does not configure AI Gateway provider proxying. Store any
   upstream credentials in Secret Manager, never in declarative config or Git.
   The platform API owns model allowlists, usage/budget enforcement, and LLM
   redaction policy.
4. Configure production OIDC/JWKS issuer/audience and test key rotation,
   expiration, invalid issuer/audience, and unauthorized routes. Avoid duplicating
   token validation in a way that disagrees between Kong and the API.
5. Connect Kong's service/backend to the global external load balancer in
   sequence 13. Do not expose Kong Admin or an unprotected API service publicly.

### Commands

```bash
helm lint deployment/helm/platform --values deployment/helm/platform/values-gcp.yaml
helm template agentops-platform deployment/helm/platform \
  --namespace "$NAMESPACE" \
  --values deployment/helm/platform/values-gcp.yaml
kubectl -n "$NAMESPACE" get svc,deploy,pods
kubectl -n "$NAMESPACE" port-forward svc/<KONG_PROXY_SERVICE> 8001:8001
```

The final command is for a controlled local Admin API inspection only; keep
that endpoint private and stop the port-forward after use. Validate the Kong
config with the selected Kong version's config validation tool in CI.

### Acceptance

- Production Kong config has no localhost issuer, demo credential, public Admin
  API, or plaintext upstream secret.
- The private API route, Kong readiness, rate/request-size limits, and denied
  request behavior are validated. Live GKE gateway requests remain an
  environment acceptance check.
- AI provider routing is deliberately not delegated to Kong OSS; platform LLM
  governance and Kong edge controls have documented, non-overlapping
  responsibility. Revisit AI Gateway only after edition/license approval.

---

## Sequence 11 — Implement OPA/Rego as a tested policy decision point

### Implement

1. Keep current Python `PolicyEngine` behavior as a baseline while defining
   policy input/output contracts. Define exactly which decisions move to OPA
   and whether OPA is embedded, a sidecar, or a private service.
2. Create versioned Rego policy files and fixtures. Inputs should be
   server-derived principal/tenant, requested action, target, risk,
   environment, approval, and current resource facts—not fields trusted from a
   model or user.
3. Deny by default for missing policy, malformed response, timeout, unavailable
   OPA, tenant mismatch, expired approval, or stale policy version. Do not
   substitute “allow” or silently fall back to Python for mutations.
4. Integrate the OPA decision at both request/admission and immediately before
   execution. Bind approval to the exact action/target and re-check policy at
   execution time.
5. Protect OPA's management/API endpoints; publish signed/versioned bundles,
   monitor bundle age, and provide controlled rollback.
6. Keep Python authorization as defense-in-depth only if ownership and
   precedence are explicit; add equivalence/regression tests during migration.

### Commands

Install/use a pinned OPA CLI in CI (do not rely on an unpinned workstation
binary), then run:

```bash
opa fmt --write policy/
opa check --strict policy/
opa test -v policy/
```

If OPA is a sidecar/service, also test the exact HTTP decision endpoint from the
API container and simulate unavailable/malformed responses. Use the
repository's established policy directory if one is added; do not commit an
OPA binary.

### Acceptance

- Rego tests cover allow, deny, approval-required, tenant isolation, missing
  permission, stale/expired approval, production critical action, and OPA
  outage.
- Mutating actions fail closed if OPA is unavailable or cannot return a valid
  decision.
- A live end-to-end test proves the same decision is checked immediately before
  execution and is recorded in the durable audit trail.

---

## Sequence 12 — Complete logs, metrics, traces, dashboards, and alerts

### Implement

1. Pick a supported GKE telemetry pipeline: Google Cloud Observability managed
   collection or an OpenTelemetry Collector deployed/managed in the cluster.
   Document where metrics, traces, and logs are exported and their retention.
2. Configure OTLP endpoint/protocol in Helm and verify the existing Python
   exporter. Remove or replace any broad silent exception around exporter
   initialization; startup/configuration failure should be visible and obey the
   chosen fail-open/fail-closed policy.
3. Export structured application logs to Cloud Logging with request/correlation
   IDs and redaction. Avoid high-cardinality metric labels (tenant/user/request
   IDs) and avoid logging prompt/secret content.
4. Scrape `/api/v1/metrics` with a configured Prometheus/managed collector.
   Enable `ServiceMonitor` only if the Prometheus Operator is actually installed;
   do not enable a CRD-dependent object without verifying the CRD.
5. Provision dashboards and alert policies (Terraform or approved config) for
   API error rate/latency, readiness, worker backlog/age, dead letters, DB,
   Redis, Pub/Sub, Vertex quota/latency/cost, policy denials/errors, and telemetry
   export failures. Route alerts to an owned on-call destination and test them.
6. Fix the observed observability test mismatch: the existing test expects
   agent-run/MCP metrics immediately after enqueue, while the actual workflow
   is asynchronous. Assert queue-enqueued metrics at enqueue time and assert
   agent/MCP execution metrics only after a worker executes the job. Do not add
   fake metrics to satisfy a stale test expectation.
7. Preserve durable audit records independently of Cloud Logging/telemetry
   outages.

### Commands

```bash
pytest backend/tests/test_observability.py backend/tests/test_health.py -q
ruff check backend/src backend/tests
helm lint deployment/helm/platform --values deployment/helm/platform/values-gcp.yaml
helm template agentops-platform deployment/helm/platform \
  --namespace "$NAMESPACE" \
  --values deployment/helm/platform/values-gcp.yaml
```

After deployment, verify logs, traces, metrics, alert policies, and a synthetic
alert in GCP:

```bash
gcloud logging read \
  'resource.type="k8s_container" AND resource.labels.namespace_name="prod"' \
  --project "$PROJECT_ID" --limit=10 --format='table(timestamp,severity,textPayload)'
gcloud monitoring policies list --project "$PROJECT_ID"
```

For an internal metrics check, keep the following port-forward running in one
terminal, then run `curl` from a second terminal:

```bash
kubectl -n "$NAMESPACE" port-forward svc/platform-api 8000:8000
```

```bash
curl --fail http://127.0.0.1:8000/api/v1/metrics
```

Use the documented Cloud Trace/Monitoring query UI or API to confirm a new
synthetic request trace is present; a configured endpoint alone is not proof.

### Acceptance

- Synthetic API request appears as a structured log, a trace with correlated
  IDs, and metrics in the intended backends.
- Dashboards and alert policies exist; at least one test alert reaches the
  owner/on-call channel and is acknowledged.
- Redaction and cardinality tests pass. Metrics do not expose secrets or
  unbounded tenant/user labels.
- Queue and workflow metric tests reflect asynchronous execution and pass.

---

## Sequence 13 — Provision the global public edge: DNS, Armor, load balancer, TLS

### Implement

1. Decide and document the public path. Recommended GCP-native path for GKE is
   a **GKE Gateway API global external managed load balancer** in front of
   Kong's proxy Service. Do not provision a second competing public ingress.
2. Enable/verify Gateway API and the required GCP APIs. Add Terraform for:
   - a global static external IP (if not managed by the controller);
   - Cloud DNS managed zone/record only for a domain/zone you own;
   - Cloud Armor security policy with baseline WAF/rate-limit rules;
   - any certificate/DNS authorization resources supported by the chosen TLS
     design.
3. Add Kubernetes Gateway/HTTPRoute and GKE `GCPBackendPolicy` resources using
   the supported GatewayClass/controller version. Bind the Cloud Armor policy
   to the Kong backend. Keep admin and internal services private.
4. Configure TLS with a supported managed-certificate or Certificate Manager
   integration, validate domain ownership, and enforce HTTPS. Set HTTP-to-HTTPS
   redirect only after HTTPS is healthy.
5. Use staging DNS/low TTL for cutover. Confirm health checks, backend
   readiness, WAF false positives, rate limits, rollback, and ownership before
   changing production DNS.
6. Terraform should own durable GCP resources; Kubernetes Gateway controller
   should own generated forwarding rules/backend services unless the selected
   design explicitly uses Terraform instead. Avoid dual ownership of generated
   resources.

### Commands

Enable/verify APIs through Terraform where possible; for diagnostics:

```bash
gcloud services list --enabled --project "$PROJECT_ID" \
  --filter='config.name=dns.googleapis.com'
gcloud services list --enabled --project "$PROJECT_ID" \
  --filter='config.name=compute.googleapis.com'
gcloud services list --enabled --project "$PROJECT_ID" \
  --filter='config.name=networkservices.googleapis.com'
gcloud compute addresses list --global --project "$PROJECT_ID"
gcloud compute security-policies list --project "$PROJECT_ID"
gcloud dns managed-zones list --project "$PROJECT_ID"
kubectl get gatewayclass
kubectl -n "$NAMESPACE" get gateway,httproute,gcpbackendpolicy
```

Before any DNS apply/cutover, inspect the exact plan:

```bash
cd infrastructure/terraform/gcp
tofu plan -input=false -var="project_id=$PROJECT_ID" \
  -var="project_name=agentops-platform" -var="environment=prod" \
  -var="region=$REGION" -var="namespace=$NAMESPACE" \
  -var="service_account_name=agentops-platform-sa-gcp" -out=tfplan
tofu show tfplan
```

After Gateway reports programmed/healthy, query the DNS name and TLS:

```bash
dig +short <APP_FQDN>
curl --fail --show-error --head "https://<APP_FQDN>/api/v1/health"
```

Also test HTTP redirect, invalid auth, allowed traffic, rate limiting, WAF
blocking, and a controlled rollback. Do not test attack payloads against
third-party or production systems without explicit authorization.

### Acceptance

- Domain resolves to the intended global external load balancer and certificate
  is valid for the hostname.
- Gateway/route/backend health is healthy; Cloud Armor policy is attached to
  the correct backend and blocking/allow rules are verified.
- Only the intended gateway is public; Kong Admin, API ClusterIP, databases,
  Redis, and internal control planes are not public.
- DNS/TLS/WAF/rate-limit cutover and rollback are documented and exercised in a
  non-production environment first.

---

## Sequence 14 — Deploy, prove health, close gaps, and declare completion

### Implement and deploy

1. Add all new dependencies to `backend/pyproject.toml` and lock/constraint
   files if used. Pin supported ranges. Update Helm, Terraform, deployment, and
   operations documentation alongside each integration.
2. Extend `.github/workflows/deploy-gcp.yml` with tests and static validation:
   Python lint/tests, frontend typecheck, Terraform/OpenTofu fmt/validate/plan,
   Helm lint/template, policy checks, and container/security scans.
3. Keep application rollout opt-in until OIDC, secrets, database, Redis,
   telemetry, Pub/Sub/queue choice, and public edge are verified. The current
   GKE smoke workflow validates scheduling/image pulls only; it is not an
   application health test.
4. Deploy a tagged immutable image (avoid `latest` for production), run
   migrations safely, verify rollouts, run authenticated smoke checks through
   the real public route, and observe a canary before full traffic.
5. Verify the production identity provider's HTTPS discovery document and
   issuer/client configuration. Keep API/gateway credentials in approved secret
   storage; do not disable auth for smoke tests.
6. Run failure-path and recovery exercises: DB unavailable, Redis unavailable,
   Pub/Sub redelivery/DLQ, Vertex quota/outage, Secret Manager denial, OPA
   unavailable, telemetry backend unavailable, and gateway rollback.
7. Update `project-scope.md` checkboxes/status only after evidence exists. Mark
   recommendations and future options separately from implemented/verified
   capabilities.

### Commands (Cloud Shell)

Run repository checks from its root:

```bash
python -m pip install -e "backend[dev]"
ruff check backend/src backend/tests
pytest backend/tests -q
cd frontend && npm ci && npm run typecheck
cd ../
helm lint deployment/helm/platform \
  --values deployment/helm/platform/values-gcp.yaml
helm template agentops-platform deployment/helm/platform \
  --namespace prod --values deployment/helm/platform/values-gcp.yaml
cd infrastructure/terraform/gcp
tofu init
tofu fmt -check
tofu validate
tofu plan -input=false -var="project_id=$PROJECT_ID" \
  -var="project_name=agentops-platform" -var="environment=prod" \
  -var="region=$REGION" -var="namespace=prod" \
  -var="service_account_name=agentops-platform-sa-gcp"
```

For rollout, use the existing protected GitHub Actions deployment workflow with
an immutable image tag and an approved `deploy_application=true`. After it
completes:

```bash
gcloud container clusters get-credentials "$CLUSTER" \
  --region "$REGION" --project "$PROJECT_ID"
kubectl -n "$NAMESPACE" get deploy,pods,svc,hpa,pdb
kubectl -n "$NAMESPACE" rollout status deploy/platform-api --timeout=10m
kubectl -n "$NAMESPACE" rollout status deploy/platform-worker --timeout=10m
kubectl -n "$NAMESPACE" rollout status deploy/platform-frontend --timeout=10m
kubectl -n "$NAMESPACE" get events --sort-by=.metadata.creationTimestamp
```

Adjust deployment names to the rendered Helm release if they differ; do not
declare success based only on a command that matched no resources. Then use
`kubectl port-forward` in a separate terminal if you need to check internal
readiness. Use authenticated synthetic requests against the public FQDN and
verify database,
Redis, queue, model, secret, policy, telemetry, and audit paths in their
respective systems.

### Acceptance checklist — only now call the 14 items complete

- [ ] Each of the 14 initial items has a named owner and evidence link (test
  output, Terraform state/plan, GCP resource, dashboard, alert, or runbook).
- [ ] Production resources are in the approved project/region and managed by
  the expected Terraform state; no unexplained drift or unreviewed changes.
- [ ] GKE application pods are ready; API/worker/frontend rollouts are
  successful; authenticated readiness and public HTTPS checks pass.
- [ ] Cloud DNS, global external load balancer, TLS, Cloud Armor, and Kong
  gateway are healthy and correctly scoped.
- [ ] Cloud SQL, Redis, GCS, Secret Manager, Vertex AI, and Pub/Sub (if selected)
  make real authenticated calls from the intended runtime identity.
- [ ] BigQuery is either proven end-to-end or explicitly documented as out of
  scope with an approved rationale.
- [ ] LLM and embedding providers are real in production; mock paths are
  limited to test/demo and cannot silently serve production traffic.
- [ ] OPA/Rego is deployed and mutation decisions fail closed; exact-action
  approvals are rechecked before execution.
- [ ] MCP tools are connected to intended providers, least-privileged, tenant
  scoped, idempotent where required, audited, and tested against denied cases.
- [ ] Logs, metrics, and traces arrive in their actual backends; dashboards and
  alert notifications are exercised; sensitive values are redacted.
- [ ] Unit, integration, security, failure-path, and deployment checks pass;
  known failures (including the asynchronous metrics assertion) are resolved.
- [ ] Backups have been restored in a recovery exercise; incident response,
  credential rotation, rollback, and operational ownership are documented.
- [ ] Documentation accurately distinguishes “implemented”, “deployed”,
  “verified”, and “not in scope”; no design recommendation is marked complete
  without runtime evidence.

## Current sequence status

This status distinguishes repository implementation from environment/live
acceptance. No production GCP deployment, DNS change, Terraform apply, or
authorized live integration test was performed during this work.

| Sequence | Repository status | Pending / blocked acceptance |
|---|---|---|
| 1 — Target and safe access | Partial; safe workflow/state checks are documented. | Approved project, state ownership, deployer IAM, OIDC settings, domain/zone ownership, and operator approval must be confirmed. |
| 2 — GCP foundation | Partial; Terraform is formatted and validates locally. | No remote-state inspection, reviewed production plan, apply, cluster access, or recovery test. |
| 3 — Cloud SQL and BigQuery | Partial; Cloud SQL and pgvector configuration/migrations exist. | BigQuery is not implemented; target PostgreSQL migration, tenant tests, and restore exercise remain. |
| 4 — GCS and RAG documents | Partial; raw-document archive adapter exists and PostgreSQL remains metadata/index authority. | External bucket, Workload Identity IAM, live upload/download/deletion, and PAC-specific ingestion remain unverified or incomplete. |
| 5 — Secret Manager | Implemented in source with the official client and Workload Identity. | Live IAM access, version rotation/restore, and GKE verification remain. |
| 6 — Redis cache | Implemented in source as an encrypted, tenant-scoped, version-bound cache. | Live Memorystore connectivity, outage behavior, and transport-security acceptance remain. |
| 7 — Pub/Sub workflow | Implemented in source with transactional outbox, consumption, retry/DLQ, and replay. | Live delivery, duplicate/redelivery, DLQ, IAM, and recovery acceptance remain. |
| 8 — Vertex AI and embeddings | Implemented in source with Vertex routing and pgvector-backed embeddings. | Live model/embedding calls, production quota behavior, and target PostgreSQL migration remain. |
| 9 — LLM Gateway | Implemented in source with tenant limits, bounded retries, quotas, and provider error handling. | Real provider health/calls, production pricing validation, and deployment configuration remain. |
| 10 — Kong Gateway | Implemented as a private Kong OSS edge with deployment checks. | Live rollout and edge traffic checks remain; Kong AI Gateway plugins are intentionally out of scope. |
| 11 — OPA/Rego | Implemented in source with Rego tests, private OPA chart deployment, fail-closed mutations, and single-use approval consumption. | Live GKE decision/audit verification, policy bundle signing, and controlled rollback remain. |
| 12 — Observability | Collector, trace export, metrics scraping, structured stdout logging, and bounded HTTP metrics are configured. | Live signal delivery, dashboards, alert policy/on-call routing, synthetic alert, and acknowledgement remain. |
| 13 — Public edge | Opt-in Terraform DNS/Cloud Armor/Certificate Manager resources and Gateway/HTTPRoute templates are present. | Domain/zone approval, reviewed plan, Gateway API/controller and cert readiness, staging tests, and production cutover remain. |
| 14 — Deploy and prove health | CI now includes Python/frontend/Helm/OPA/OpenTofu checks and image scanning. | Full CI acceptance, unresolved baseline test failures, authenticated public smoke tests, restore/failure exercises, and production evidence remain. |

**Completion statement:** Only after every applicable check above is backed by
evidence should the project be described as implemented end-to-end. A checklist
with checked source-code boxes alone is not a production completion record.
