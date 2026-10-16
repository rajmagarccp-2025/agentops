# Architecture Implementation Map

## Overview
This document maps every target architecture component in the **Cloud-Agnostic Agentic SRE, FinOps & LLMOps Platform** to its actual implementation file, public entry point, execution path, and validation status.

---

## 1. User Interface and API Layer

| Component | Implementation File(s) | Public Entry Point / Export | Status | Execution Path |
| :--- | :--- | :--- | :--- | :--- |
| **Next.js Web UI** | `frontend/src/app/*` | `npm run dev` / Next.js App Router | `PASS` | `Browser -> Next.js App Router -> React Server/Client Components -> Axios/Fetch -> FastAPI` |
| **FastAPI API Layer** | `backend/src/platform_api/main.py` | `app = FastAPI()` | `PASS` | `Uvicorn ASGI -> main.py -> APIRouter Endpoints` |
| **Request Validation & Error Handling** | `backend/src/platform_api/errors.py` | `application_error_handler`, `ApplicationError` | `PASS` | `FastAPI exception handlers -> JSONResponse with structured detail` |
| **Authentication & Authorization (OAuth2/OIDC/JWT)** | `backend/src/platform_api/security.py`, `platform_api/api/auth.py` | `get_current_user`, `require_permission` | `PASS` | `Bearer Token -> JWT decode -> Principal RBAC validation` |
| **RBAC & Multi-Tenancy Engine** | `backend/src/platform_api/identity_models.py`, `identity_repository.py` | `IdentityRepository` | `PASS` | `User/Role/Tenant DB queries -> Permission check per endpoint` |
| **Session Management & Token Handling** | `backend/src/platform_api/middleware.py` | `RequestIdMiddleware`, `enforce_demo_read_only` | `PASS` | `HTTP Request Middleware -> Context propagation -> Claims verification` |

---

## 2. Agent Orchestration Layer

| Component | Implementation File(s) | Public Entry Point / Export | Status | Execution Path |
| :--- | :--- | :--- | :--- | :--- |
| **LangGraph Supervisor / Router** | `backend/src/platform_api/agents/runtime.py` | `AgentOrchestrator.run()` | `PASS` | `API -> AgentOrchestrator -> LangGraph StateGraph -> Supervisor Node` |
| **Specialist Agent Registration & Nodes** | `backend/src/platform_api/agents/nodes.py` | `supervisor_node`, specialist nodes | `PASS` | `Supervisor decision -> Node function dispatch -> Tool execution -> State update` |
| **State Management & Context Propagation** | `backend/src/platform_api/agents/state.py`, `models.py` | `AgentState`, `AgentExecutionRequest` | `PASS` | `TypedDict state schema passed through LangGraph memory checkpointer` |
| **Conditional & Parallel Execution** | `backend/src/platform_api/agents/runtime.py` | `build_graph()` | `PASS` | `LangGraph conditional edges -> Supervisor routing decision` |
| **Retry, Timeout & Failure Recovery** | `backend/src/platform_api/agents/runtime.py` | `AgentOrchestrator._execute_with_timeout()` | `PASS` | `Asyncio timeout wrapper -> Error capture -> Graceful failure state` |
| **Agent Execution Tracing & Auditing** | `backend/src/platform_api/observability.py` | `trace_agent_execution` | `PASS` | `OpenTelemetry tracer span -> Structured logs & metrics` |

---

## 3. Specialist Agents

| Agent | Node / Implementation File | Backend Service / Domain Module | Status | Execution Path |
| :--- | :--- | :--- | :--- | :--- |
| **1. Discovery & Inventory Agent** | `nodes.py` (`discovery_agent_node`) | `platform_api/inventory/service.py` | `PASS` | `Supervisor -> discovery_agent_node -> InventoryService -> Cloud Adapters` |
| **2. SRE / Incident Intelligence Agent** | `nodes.py` (`sre_incident_agent_node`) | `platform_api/incidents/service.py` | `PASS` | `Supervisor -> sre_incident_agent_node -> IncidentService -> Telemetry & Alerts` |
| **3. FinOps & Capacity Optimization Agent** | `nodes.py` (`finops_agent_node`) | `platform_api/finops/service.py` | `PASS` | `Supervisor -> finops_agent_node -> FinOpsService -> Cloud Cost Adapters` |
| **4. Remediation Agent** | `nodes.py` (`remediation_agent_node`) | `platform_api/remediation/service.py` | `PASS` | `Supervisor -> remediation_agent_node -> PolicyEngine -> ApprovalService -> Executor` |
| **5. LLMOps Agent** | `nodes.py` (`llmops_agent_node`) | `platform_api/llmops_service/service.py` | `PASS` | `Supervisor -> llmops_agent_node -> LLMOpsService -> Gateway Metrics` |
| **6. Security Investigation Agent** | `nodes.py` (`security_investigation_agent_node`) | `platform_api/security_investigation/service.py` | `PASS` | `Supervisor -> security_investigation_agent_node -> SecurityService -> Security Logs` |
| **7. Change Intelligence Agent** | `nodes.py` (`change_intelligence_agent_node`) | `platform_api/changes/service.py` | `PASS` | `Supervisor -> change_intelligence_agent_node -> ChangeService -> Deployment/Git Logs` |

---

## 4. Platform Services

| Service | Implementation File(s) | Public Entry Point / Interface | Status | Execution Path |
| :--- | :--- | :--- | :--- | :--- |
| **Policy / Risk Engine** | `platform_api/governance/policy_engine.py` | `PolicyEngine.evaluate()` | `PASS` | `Remediation Request -> Policy Engine rules -> Risk Level & Approval Requirement` |
| **Human Approval Engine** | `platform_api/governance/approval_service.py` | `ApprovalService.create_approval_request()` | `PASS` | `Risk Evaluation -> Approval Record -> Human JWT Sign -> Re-authorization Check` |
| **OpenTelemetry Instrumentation** | `platform_api/observability.py` | `configure_observability()` | `PASS` | `FastAPI / LangGraph / HTTP Clients -> W3C Tracecontext -> OTEL Exporter` |
| **RAG Service & Vector DB** | `platform_api/rag_service/` | `RagService.ingest_document()`, `retrieve()` | `PASS` | `Document -> Chunking -> Embedding -> pgvector (SQLAlchemy) -> Cosine Reranking` |
| **LLM Gateway** | `platform_api/llm/` | `LLMGateway.generate_completion()` | `PASS` | `Gateway Request -> Provider Router -> Token Accounting & Circuit Breaking -> Model API` |
| **MCP Gateway** | `platform_api/mcp/` | `MCPGateway.execute_tool()` | `PASS` | `Agent -> MCP Tool Spec -> Schema Validation -> Authorized Adapter Execution` |
| **PostgreSQL & Migrations** | `platform_api/database.py`, `backend/migrations/` | `get_db_session()`, `alembic upgrade` | `PASS` | `SQLAlchemy 2.0 Async/Sync -> PostgreSQL database session` |
| **Redis Cache & State** | `platform_api/redis_client.py` | `get_redis_client()` | `PASS` | `Redis Client -> Key-Value Cache / Session State` |
| **Audit Service** | `platform_api/governance/audit_service.py` | `AuditService.log_event()` | `PASS` | `Security / Mutation Action -> Structured Audit Log -> DB Audit Table` |

---

## 5. External Integrations

| Provider / Adapter | Implementation File(s) | Status | Test / Mock Strategy |
| :--- | :--- | :--- | :--- |
| **LLM Providers (OpenAI, Gemini, Anthropic)** | `platform_api/llm/providers.py` | `PASS` | Live credentials when configured; MockProvider fallback for CI |
| **AWS Adapter** | `platform_api/integrations/aws_adapter.py` | `PASS` | Boto3 client mock & live STS/CloudWatch sandbox integration |
| **GCP Adapter** | `platform_api/integrations/gcp_adapter.py` | `PASS` | Google Cloud SDK mock & live API service account integration |
| **Azure Adapter** | `platform_api/integrations/azure_adapter.py` | `PASS` | Azure SDK mock & live Service Principal integration |
| **Kubernetes Adapter** | `platform_api/integrations/kubernetes_adapter.py` | `PASS` | In-cluster / kubeconfig client & mock fallback |
| **CI/CD & GitHub Adapter** | `platform_api/integrations/github_adapter.py` | `PASS` | PyGithub client & webhook integration |
