# Rollback Runbook

## Decision

Rollback when health/readiness fails, error rate or latency breaches the service
objective, data integrity is at risk, or a release causes unsafe agent/tool behavior.

## GitOps rollback

1. Identify the last known good commit or image digest.
2. Revert the GitOps source change or select the known-good Argo CD revision.
3. Sync and monitor:
	```text
	kubectl -n argocd get application agentic-platform-prod
	kubectl -n agentic-platform-prod rollout status deployment/platform-api
	```
4. Validate `/api/v1/health`, `/api/v1/health/ready`, and `/api/v1/metrics`.

## Controlled application rollback

Use the remediation API only for allowlisted rollback actions. Production rollback
requires policy approval, an idempotency key, and post-action verification.

## Database caution

Application rollback does not automatically roll back database migrations. Confirm
backward compatibility first. Restore data only through the database recovery
runbook and provider-approved backup procedures.
