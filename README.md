# Cloud-Agnostic Agentic SRE, FinOps & LLMOps Platform

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-green.svg)](https://www.python.org/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-1.28+-blue.svg)](https://kubernetes.io/)
[![Helm](https://img.shields.io/badge/Helm-v3-blue.svg)](https://helm.sh/)
[![Argo CD](https://img.shields.io/badge/Argo_CD-GitOps-orange.svg)](https://argoproj.github.io/cd/)

An enterprise-grade, cloud-agnostic platform powered by autonomous specialist agents that continuously discover cloud infrastructure, correlate incidents, telemetry, deployments, configuration changes, security findings, costs, and LLM/GPU consumption. The platform investigates root causes, delivers evidence-backed remediation recommendations, simulates operational impact, and executes governed infrastructure mutations strictly requiring authenticated human approval.

---

## 🌟 Key Features & Capabilities

- **Discovery Agent**: Automatic inventory discovery, normalization, dependency mapping, and freshness tracking across AWS, GCP, Azure, OpenShift, Kubernetes, and GitHub.
- **Incident Intelligence Agent**: Real-time incident correlation, root-cause analysis, and telemetry synthesis across OpenTelemetry logs, metrics, and traces.
- **Change Intelligence Agent**: Correlates deployments, configuration changes, and IaC modifications without assuming temporal causality.
- **Security Investigation Agent**: Non-mutating correlation of IAM activity, security findings, and threat indicators.
- **FinOps & Capacity Optimization Agent**: Rightsizing recommendations, scheduling, commitment analysis, and capacity optimization with explicit cost calculations.
- **LLMOps & Telemetry Agent**: Monitors model latency, token usage, cost, prompt drift, retrieval quality, tool calls, and provider performance regression.
- **Human-in-the-Loop Governance Plane**: Non-bypassable policy engine, RBAC, single-use exact-action approvals, fail-closed mutation control, and execution-time re-authorization.
- **MCP Gateway & Provider Adapters**: Decoupled tool execution boundaries ensuring agent runtimes never access raw credentials or cloud SDKs.
- **Access-Aware RAG Engine**: Multi-tenant knowledge indexing and vector retrieval enforcing RBAC boundaries on document contexts.

---

## 🛠 Tech Stack

| Domain | Technology / Framework |
| :--- | :--- |
| **Frontend** | Next.js 15, TypeScript, React 19, Tailwind CSS, Lucide Icons |
| **Backend API** | Python 3.12, FastAPI, Asyncio, Pydantic v2, SQLAlchemy 2.0 |
| **Agent Orchestration** | LangGraph, LangChain, Custom State Machine Runtimes |
| **Databases & Cache** | PostgreSQL 16 (Alembic Migrations), Redis 7 (State & Caching) |
| **Tool & Provider Interop** | Model Context Protocol (MCP), AWS/Azure/GCP Provider Adapters |
| **Observability** | OpenTelemetry, Prometheus, ServiceMonitors, W3C Tracecontext |
| **Packaging & GitOps** | Docker (Multi-Stage Non-Root), Helm 3, Argo CD, Terraform |

---

## 🏗 Architecture Overview

```
                          ┌──────────────────────────┐
                          │   Next.js 15 Frontend    │
                          └────────────┬─────────────┘
                                       │ REST / WSS
                                       ▼
                          ┌──────────────────────────┐
                          │    FastAPI Gateway       │
                          └────────────┬─────────────┘
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
  ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
  │ Governance Plane │       │ Agent Supervisor │       │   LLM Gateway    │
  │ (Policy & RBAC)  │       │   (LangGraph)    │       │ (Router/Fallback)│
  └─────────┬────────┘       └─────────┬────────┘       └──────────────────┘
            │                          │
            ▼                          ▼
  ┌──────────────────┐       ┌──────────────────┐
  │ Approval Service │       │   MCP Gateway    │
  │ (Human-in-Loop)  │       │ (Tool Boundary)  │
  └─────────┬────────┘       └─────────┬────────┘
            │                          │
            └──────────┬───────────────┘
                       ▼
          ┌──────────────────────────┐
          │     Provider Adapters    │
          │ (AWS, GCP, Azure, K8s)   │
          └──────────────────────────┘
```

---

## 📋 Prerequisites

Before setting up the project locally, ensure you have the following installed:

- **Node.js**: `v20.x` or `v22.x`
- **Python**: `v3.12.x`
- **Docker & Docker Compose**: `v24.0+`
- **Helm**: `v3.12+` (for deployment testing)
- **kubectl**: `v1.28+`

---

## ⚙️ Environment Configuration

Copy `.env.example` to `.env` in the root directory:

```bash
cp .env.example .env
```

### Essential Environment Variables

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `ENVIRONMENT` | Operational stage (`development`, `staging`, `production`) | `development` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://platform:platform_pass@localhost:5432/platform_db` |
| `REDIS_URL` | Redis cache & state connection string | `redis://localhost:6379/0` |
| `JWT_SECRET_KEY` | Secret key for signing authorization tokens | `super-secret-jwt-token-key-change-in-production` |
| `DEFAULT_TENANT_ID` | Default multi-tenant scope | `tenant-a` |
| `OPENAI_API_KEY` | Optional OpenAI provider API key | `sk-proj-...` |
| `GEMINI_API_KEY` | Optional Google Gemini provider API key | `AIzaSy...` |
| `ANTHROPIC_API_KEY` | Optional Anthropic Claude provider API key | `sk-ant-...` |

---

## 🚀 Local Development Setup

### 1. Start Infrastructure Services

Spin up PostgreSQL, Redis, and MinIO storage locally using Docker Compose:

```bash
docker compose up -d postgres redis s3server
```

### 2. Set Up Backend API

```bash
# Create and activate Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install backend dependencies in editable mode
pip install -e ./backend
pip install -r backend/requirements-dev.txt

# Run database migrations
cd backend
alembic upgrade head
cd ..

# Start FastAPI development server
uvicorn platform_api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API documentation is available at `http://localhost:8000/docs`.

### 3. Set Up Frontend Web Application

```bash
cd frontend

# Install Node dependencies
npm ci

# Start Next.js development server
npm run dev
```

The Web UI is available at `http://localhost:3000`.

---

## 🐳 Production Deployment & GitOps Guide

### Containerization

Build non-root multi-stage production Docker images:

```bash
# Build API container image
docker build -t platform-api:1.0.0 -f docker/backend.Dockerfile .

# Build Worker container image
docker build -t platform-worker:1.0.0 -f docker/worker.Dockerfile .

# Build Frontend container image
docker build -t platform-frontend:1.0.0 -f docker/frontend.Dockerfile .
```

### Helm Deployment

Deploy using the cloud-agnostic application Helm chart:

```bash
# Validate chart syntax
helm lint deployment/helm/platform

# Deploy to Kubernetes cluster with GCP overlay
helm install platform deployment/helm/platform -n platform-prod --create-namespace -f deployment/helm/platform/values-gcp.yaml
```

### GitOps with Argo CD

Deploy the Argo CD Application to manage continuous reconciliation from Git:

```bash
kubectl apply -f deployment/argocd/project.yaml
kubectl apply -f deployment/argocd/application.yaml
```

---

## 🧪 Testing & Verification

Run the comprehensive platform test suite:

```bash
# Execute backend unit and integration tests
pytest backend/tests

# Run platform security proof assertions
pytest backend/tests/test_platform_security_proofs.py

# Execute frontend TypeScript check & Next.js build validation
cd frontend && npm run typecheck && npm run build
```

---

## 📄 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
