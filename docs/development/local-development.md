# Local Development

## Prerequisites

- Python 3.12
- Node.js 22 and npm 10
- Docker Desktop with Compose v2
- GNU Make, or PowerShell equivalents for the commands in `Makefile`

## Setup

Copy `.env.example` to `.env`, then run:

```text
make setup
```

This creates the Python virtual environment, installs backend development
dependencies, and installs frontend dependencies.

## Start the local stack

```text
make docker-up
```

The Phase 0 services are:

- Web UI: `http://localhost:3000`
- API: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`
- API health: `http://localhost:8000/api/v1/health`
- PostgreSQL with pgvector: `localhost:5432`
- Redis: `localhost:6379`
- OTLP gRPC: `localhost:4317`
- OTLP HTTP: `localhost:4318`

Stop the stack with `make docker-down`.

## Validation

```text
make lint
make typecheck
make test
make migrate
docker compose config
```

The migration command requires the PostgreSQL Compose service to be running.
The local API includes mock MCP tools, mock LLM providers, LangGraph workflows,
RAG, FinOps, security investigation, approval-gated remediation, verification,
and learning paths without cloud credentials. Browser E2E coverage and real cloud
provider adapters remain follow-up work.

Seed the local in-memory demo scenario with:

```text
make seed
```

Run the complete backend smoke suite with:

```text
make integration-test
```
