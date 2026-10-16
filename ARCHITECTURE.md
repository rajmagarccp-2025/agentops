# Architecture Overview

This document is the high-level architecture index for the Cloud-Agnostic Agentic
SRE, FinOps & LLMOps Platform. It intentionally stays high-level and links out to
detailed documents rather than duplicating content.

## Core lifecycle

```
DISCOVER -> OBSERVE -> CORRELATE -> INVESTIGATE -> EXPLAIN -> RECOMMEND
-> SIMULATE -> RISK/POLICY CHECK -> HUMAN APPROVAL -> REMEDIATE -> VERIFY -> LEARN
```

## Top-level flow

```
User -> Next.js -> FastAPI -> OAuth2/OIDC/RBAC -> LangGraph Supervisor/Router
-> Specialist Agents -> RAG/Knowledge -> MCP Gateway -> Cloud/Infrastructure/Observability tools
```

## Specialist agents

1. Discovery & Inventory Agent
2. SRE / Incident Intelligence Agent
3. FinOps & Capacity Optimization Agent
4. LLMOps Agent
5. Security Investigation Agent
6. Change Intelligence Agent
7. Remediation Agent

Security and Governance are **cross-cutting controls**, not agents in the sequential chain.

## Platform services (not agents)

- MCP Gateway
- LLM Gateway
- Policy / Risk Engine
- Approval Engine
- RAG Service
- Vector Database (pgvector)
- PostgreSQL
- Redis
- OpenTelemetry
- Audit Service

## Detailed documentation

| Area | Location |
|---|---|
| System / component / deployment architecture | [docs/architecture/](./docs/architecture) |
| Agent catalog, responsibilities, workflows | [docs/agents/](./docs/agents) |
| RAG design | [docs/rag/](./docs/rag) |
| LLMOps design | [docs/llmops/](./docs/llmops) |
| MLOps design | [docs/mlops/](./docs/mlops) |
| Evaluation strategy | [docs/evaluation/](./docs/evaluation) |
| Security model | [docs/security/](./docs/security) |
| Operations & runbooks | [docs/operations/](./docs/operations), [docs/runbooks/](./docs/runbooks) |

## Architectural rules

- Agents are **not** allowed to directly access cloud APIs — all access goes through the **MCP Gateway**.
- Agents are **not** allowed to directly call LLM providers — all access goes through the **LLM Gateway**.
- High-risk actions **must** require human approval.
- The LLM reasons over evidence; it is never the sole source of correlation truth.
- No arbitrary LLM-generated shell command may be executed against production.

> Status: **Implemented foundation** — executable backend, frontend, gateway,
> agent, governance, RAG, FinOps, security, observability, deployment, and
> infrastructure boundaries are present. Provider-specific production rollout
> still requires cloud credentials, remote state, and cluster installation.
