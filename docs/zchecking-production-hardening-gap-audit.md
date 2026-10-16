# Production hardening implementation status for `zchecking.md`

This audit maps the seven numbered priority areas in `zchecking.md` to the
implemented controls and the limits that remain. It is an implementation status,
not a claim that external production infrastructure has been provisioned.

## Priority and section mapping

| `zchecking.md` section | Status | Implemented controls | Remaining operational boundary |
| --- | --- | --- | --- |
| 01 — Tenant isolation and authorization | Strengthened | Workflow jobs and run reads are tenant-scoped; durable run/step records preserve tenant, project, and environment context; tool idempotency is tenant/tool scoped and binds request parameters plus project/environment; secret runtime resolution checks scope. | Continue applying tenant/project/environment filters to new data surfaces and run authorization regression tests whenever those surfaces change. |
| 02 — Durable workflow execution | Implemented for queued agent jobs | LangGraph checkpoints use the configured PostgreSQL or SQLite database; agent requests enter a durable queue; workers claim jobs with leases, recover expired leases, enforce bounded retries and timeouts, support cancellation, and dead-letter exhausted jobs. A retry resumes an existing LangGraph checkpoint rather than unconditionally starting at the graph beginning. Queue capacity and worker concurrency are bounded. | PostgreSQL/SQLite persistence is only as durable as its deployment, backup, and restore configuration. Recovery from a crash inside a non-idempotent external operation still depends on that provider's idempotency contract. |
| 03 — Tool security and remediation safety | Strengthened | Tool audit persistence fails closed; parameters are redacted; started, failed, and completed executions are recorded; persisted replay keys reject changed requests and concurrent duplicate execution. Remediation jobs are not automatically retried unless marked safe. | Database idempotency cannot guarantee exactly-once effects for external providers that do not support idempotency or reconciliation. |
| 04 — Integration and credential isolation | Lifecycle controls implemented; external integrations blocked in production | Secrets have explicit expiry/revocation state; expired or revoked versions cannot be resolved; revoked records cannot be modified; scope checks are enforced; lifecycle scans emit rotation-due/expiry events. The internal encrypted provider remains available. | AWS, Azure, GCP, and Vault adapter classes are scaffolds rather than live SDK integrations; production now rejects them with HTTP 503 instead of reporting mock success. Real SDK operations, unattended rotation, and provider-side revocation require provider-specific implementation and credentials. |
| 05 — LLM and dependency resilience | Partially implemented | Durable queue backpressure, bounded job retries, worker timeouts, and configured LLM retry/timeout settings limit several failure modes. | Provider failover/circuit breaking, dependency-specific retry classification, and end-to-end resilience testing against real providers remain deployment/integration work. |
| 06 — Observability and evaluation | Strengthened | Durable per-tenant hash-chained audit events and a verification endpoint; tool and workflow counters; queue-depth/status and worker-heartbeat metrics; worker-aware readiness; critical counters/logging for queue saturation and dead-lettering. | Alert counters and logs need a configured external metrics/logging alert route and on-call ownership. No notification delivery or fully automated incident-recovery workflow is bundled. |
| 07 — Tenant-aware data lifecycle | Partially implemented | Secret expiry scans and a configurable audit archival-copy age are implemented. Archived audit entries are immutable at the database layer and checked against their source records during chain verification. | Audit archival currently copies rather than removes rows, preserving full-chain verification but not reducing the hot-table footprint. External WORM storage/signed checkpoints, tenant deletion/export policies, and tested backup/restore/data-residency policies require infrastructure and product policy decisions. |

## Operational configuration and deployment

- Apply Alembic migrations through the latest revision before starting API and
  worker processes. `init_db()` creates missing tables but is not a substitute
  for applying schema migrations to an existing deployment.
- Configure `DATABASE_URL`, Redis, worker concurrency, queue capacity, job
  timeout/lease, secret lifecycle scan interval, and audit archival age for each
  environment. Do not use local SQLite for a multi-worker production deployment.
- Run at least one worker alongside the API. `/health/ready` reports a degraded
  state when no current workflow-worker heartbeat is present.
- Configure backups, restore drills, external telemetry export, alert routing,
  provider SDK integrations, and secret rotation/revocation procedures before
  production launch. External provider adapter scaffolds are intentionally
  disabled in production.

## Validation coverage

Regression coverage includes durable queue idempotency and tenant isolation,
retry/dead-letter and lease recovery, cancellation, audit-chain verification
and archive-copy integrity, tool idempotency scoping, agent-run queue execution,
and secret lifecycle enforcement. These tests do not replace multi-process
PostgreSQL/Redis integration tests or disaster-recovery drills.
