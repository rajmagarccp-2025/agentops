# Incident Runbook

## Scope

Use this runbook for service incidents involving the platform API, web console,
agent workflows, MCP tools, LLM Gateway, database, Redis, or Kubernetes deployment.

## Triage

1. Confirm impact and severity. Record tenant, service, environment, start time,
	request IDs, and the last known good release.
2. Check health and metrics:
	```text
	curl https://app.example.com/api/v1/health
	curl https://app.example.com/api/v1/health/ready
	curl https://app.example.com/api/v1/metrics
	```
3. Inspect Kubernetes state:
	```text
	kubectl -n agentic-platform get pods,svc,events
	kubectl -n agentic-platform describe deployment platform-api
	kubectl -n agentic-platform logs deployment/platform-api --since=30m
	```
4. Check recent deployments and changes through `/api/v1/changes/{service}`.
5. For an incident record, use `/api/v1/incidents` and run its investigation
	endpoint. The investigation collects telemetry through MCP and correlates
	changes before invoking the LLM.

## Containment

- Stop unsafe automation by rejecting or withholding pending approvals.
- Keep remediation in dry-run until evidence supports a controlled action.
- Scale only through the MCP Gateway and approval workflow.
- Do not execute generated shell commands or direct cloud SDK calls.

## Recovery

Use the remediation endpoint for allowlisted restart, scale, or rollback actions.
High-risk actions create approval requests. After execution, verify with the
learning verification endpoint and record operator feedback.

## Closeout

Record timeline, evidence, change correlation, approval decisions, action outcome,
verification metrics, and follow-up labels. Preserve request IDs and trace IDs.
