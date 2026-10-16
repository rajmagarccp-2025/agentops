# AI Agent Runbook

## Safety boundaries

Agents use only the LLM Gateway and MCP Gateway. They must not call provider SDKs,
cloud APIs, Kubernetes, Terraform, shell commands, ITSM, or CI/CD directly.

## Inspect a run

```text
GET /api/v1/agent-runs/{run_id}
GET /api/v1/metrics
```

Review supervisor routing, evidence, tool calls, LLM telemetry, approvals, and
checkpoint state. Treat LLM output as reasoning, not observed fact.

## Stuck or unsafe run

1. Stop further approvals and mark the run for investigation.
2. Inspect the checkpoint and last step.
3. Confirm the tenant and permissions on every tool call.
4. Reject pending high-risk approvals if evidence is insufficient.
5. Resume only through the approved workflow path.

## Evaluation

Record groundedness, correctness, retrieval quality, tool-call correctness, cost,
latency, and operator feedback through the LLMOps and learning APIs.
