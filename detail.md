GCP Enterprise Agentic AI Platform — Client Architecture
1. Project overview
Project objective: Build a secure, multi-tenant AI operations platform on Google Cloud that uses specialist AI agents to investigate incidents, discover cloud resources, optimize costs, investigate security issues, assess changes, and execute approved remediations.

The platform runs on GKE Autopilot, uses Vertex AI for model inference, and integrates with Google Cloud and external operational systems. GitHub, Terraform, Helm, and Argo CD provide the infrastructure and application delivery pipeline.

The core design principle is to use each resource for one clear responsibility rather than deploy multiple services that solve the same problem.



3. End-to-end application flow
Consider a user asking:

“Investigate why my production Kubernetes application is slow and recommend a safe fix.”
01

The user enters the platform

Cloud DNS resolves the application hostname. The global load balancer terminates HTTPS, and Cloud Armor filters unwanted traffic before it reaches the application.



02

The gateway routes the request

Kong routes the request to Next.js, FastAPI, or the Keycloak login flow. Each service has a distinct responsibility; Kong is the only API gateway.



03

The API validates access

FastAPI validates the access token, checks organization/project/environment membership, and records the requested workflow in Cloud SQL.



04

A durable investigation begins

The request is published to Pub/Sub. A worker starts the LangGraph workflow and loads or checkpoints its execution state in PostgreSQL.



05

Agents collect evidence

The SRE agent queries live metrics, logs and Kubernetes APIs. RAG retrieves authorized runbooks and previous incident reports. Vertex AI supports analysis and synthesis.



06

Policies control the action

If a fix is proposed, OPA evaluates the operation and its scope. High-risk operations pause for an authorized human decision.



07

MCP executes approved tools

The internal MCP gateway validates the exact tool, arguments, resource scope and identity before invoking an authorized integration.



08

The outcome is verified

The workflow checks the actual deployment, workload health, latency and error rates. It records evidence, updates the incident, and reports the result.



09

The platform is monitored

OpenTelemetry instrumentation sends relevant traces, metrics and logs to Google Cloud observability services. Errors, cost, latency and security events trigger alerts.



The key safety rule is that an AI-generated recommendation never grants permission to perform an action. Authorization, policy evaluation and approval are enforced by application services before the tool executes.

4. GCP resources used and the problem each solves
This table is the client-facing resource inventory. It distinguishes Google Cloud resources from application components running inside GKE and external delivery tools.
A. Networking and application access
Resource	Why it is used	What it replaces or avoids
GCP project and IAM	Organize resources, control access, manage billing and permissions.	Avoids broad, unmanaged access across all resources.
VPC and subnets	Provide private network connectivity for GKE and managed services.	Avoids exposing databases and internal services publicly.
Private Google Access / Cloud NAT	Allow private workloads to reach Google APIs and, when required, approved internet destinations. Use Cloud NAT only when needed by the network design.	Avoids unnecessary public IPs for application workloads.
Cloud DNS	Map the application hostname to the static public IP address.	Avoids unmanaged DNS configuration.
Global external Application Load Balancer	Provides global HTTPS entry, routing and load distribution to the GKE application.	Avoids building your own Internet-facing load balancer.
Certificate Manager	Manages Google-managed TLS certificates for supported global load-balancer configurations.	Avoids manual certificate renewal.
Cloud Armor	Applies edge WAF rules, filtering and rate limiting.	Blocks common web attacks before they reach application pods.
GKE Gateway API	Lets Kubernetes configuration manage the load balancer and its routes.	Avoids separately maintaining overlapping load-balancer routing definitions.
Kong Gateway + AI Gateway	Central API gateway and AI traffic gateway, deployed as one logical gateway platform.	Avoids operating separate API and LLM gateway products with overlapping responsibilities.

Cloud Armor protects at the edge; FastAPI still performs business-level authorization. These are complementary controls, not duplicates. 

Google Cloud Documentation
+2



B. Application runtime and AI services
Component / resource	Why it is used	Placement
GKE Autopilot	Runs and scales containerized applications without requiring you to manage worker-node infrastructure directly.	Managed GKE cluster. 

Google Cloud Documentation
Next.js + TypeScript	User dashboard, chat, run history and approval interface.	GKE Deployment
FastAPI + Pydantic	API contracts, request validation, tenant context and application authorization.	GKE Deployment
Keycloak	User login, OIDC, enterprise federation and identity lifecycle.	GKE Deployment
LangGraph Supervisor and workers	Orchestrate specialist agent workflows and persistent checkpoints.	GKE Deployments
OPA / Rego policy service	Deterministic authorization and risk-policy decisions.	Internal GKE Deployment
Approval and Audit services	Persist approvals, action decisions and business audit events.	Application services in GKE, backed by Cloud SQL
Internal MCP Gateway and MCP servers	Authenticate and constrain tool calls to cloud, Kubernetes, ITSM and operational integrations.	Private GKE Services
RAG service and ingestion workers	Ingest knowledge, retrieve authorized evidence and assemble grounded context.	GKE Deployments
OpenTelemetry Collector	Receives, filters and exports telemetry from instrumented applications.	GKE Deployment

These logical services do not each need their own GCP managed product. They can be independently deployed as Kubernetes workloads when operationally justified.

Important separation: Keycloak manages identity, Kong controls gateway traffic, OPA makes policy decisions, and MCP controls tool execution. Do not make all four services independently implement the same business permission rules.
C. Data, AI and integration resources
GCP resource	Why it is used	Design boundary
Cloud SQL for PostgreSQL + pgvector	Stores application records, workflow checkpoints, approval state, tenant metadata and vector-index data.	One primary database technology; use separate databases/schemas and least-privilege roles.
Memorystore for Redis	Cache, short-lived coordination and rate-limit counters where appropriate.	Not the authoritative record for workflows, approvals or audit history.
Pub/Sub	Delivers asynchronous work and integration events to workers.	One event-messaging platform; configure retries, dead-letter handling and idempotent consumers.
Cloud Storage	Stores source documents, uploaded knowledge, parsed artefacts and evaluation datasets.	Durable object storage, not a replacement for transactional database records.
Vertex AI	Provides approved models for reasoning, classification, generation and embeddings.	One primary managed model platform; route calls through Kong's AI capabilities.
Secret Manager	Stores provider credentials, client secrets, passwords and sensitive integration configuration.	Never put secret values in source control or images.
Cloud KMS	Provides customer-managed encryption keys where required by compliance or security policy.	KMS manages keys; Secret Manager stores secret values.
GKE Workload Identity Federation	Allows workloads to access authorized Google Cloud APIs without distributing long-lived service-account key files.	Use separate Kubernetes service accounts and least-privilege IAM bindings.

Cloud SQL connectors provide authorized, encrypted connections to Cloud SQL. Use a supported connector or Auth Proxy configuration, private connectivity where feasible, connection pooling, and controlled access. 

Google Cloud Documentation
+1




Secret Manager already encrypts stored secrets; introduce customer-managed keys where there is a clear requirement, rather than creating custom encryption logic. 

Google Cloud Documentation
+1




Pub/Sub handles redelivery and retry policies, so the worker design must tolerate duplicate message delivery. 

Google Cloud Documentation
+1



D. Observability, discovery and delivery
Resource / tool	Why it is used	What it owns
Cloud Logging	Central application, integration and platform logs.	Log records
Cloud Monitoring	Metrics, dashboards, alert policies and SLO monitoring.	Operational metrics
Cloud Trace	End-to-end request latency and distributed traces.	Trace spans
Cloud Audit Logs	Records relevant Google Cloud control-plane and access activity.	GCP audit trail
Cloud Asset Inventory	Searches cloud resource metadata and helps detect inventory drift.	GCP resource discovery metadata
Artifact Registry	Stores versioned Docker images used by GKE.	Immutable container artifacts
Terraform	Provisions GCP infrastructure declaratively.	Cloud infrastructure definitions
GitHub Actions	Tests code, scans dependencies and images, and builds/publishes artifacts.	CI pipeline
Helm	Packages Kubernetes workloads and environment-specific configuration.	Kubernetes deployment templates
Argo CD	Pulls approved GitOps configuration and synchronizes it into GKE.	Application deployment state
GitHub Workload Identity Federation	Gives approved GitHub Actions workflows short-lived access to GCP.	CI identity, separate from GKE workload identity

Cloud Monitoring and Cloud Trace solve different observability problems: one focuses on metrics and alerting, while the other traces an individual request across services. 

Google Cloud Documentation
+1




Cloud Asset Inventory is useful for broad discovery, but Google documents that it is not intended for real-time asset queries where stale results could affect availability or security. Use live provider APIs to verify current operational state. 

Google Cloud Documentation



Resources deliberately not added
To avoid unnecessary duplication, the baseline does not add Cloud Run, App Engine, a second API gateway, a self-hosted database, a self-hosted message broker, a separate vector database, or another Kubernetes platform.

One additional capability may be justified later: BigQuery for detailed cloud billing-export analytics if the FinOps agent needs historical SKU-level cost analysis beyond the initial billing APIs and budget monitoring. It should be an explicit scope decision, not an unplanned baseline dependency.


5. GitHub → Terraform → Helm → Argo CD deployment flow
This is how your team releases application changes and infrastructure changes without allowing two tools to manage the same resource.
#chatgpt-mermaid-_r_2m0_{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;fill:rgb(237, 237, 237);}@keyframes edge-animation-frame{from{stroke-dashoffset:0;}}@keyframes dash{to{stroke-dashoffset:0;}}#chatgpt-mermaid-_r_2m0_ .edge-animation-slow{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 50s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-_r_2m0_ .edge-animation-fast{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 20s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-_r_2m0_ .error-icon{fill:rgb(48, 48, 48);}#chatgpt-mermaid-_r_2m0_ .error-text{fill:rgb(237, 237, 237);stroke:rgb(237, 237, 237);}#chatgpt-mermaid-_r_2m0_ .edge-thickness-normal{stroke-width:1px;}#chatgpt-mermaid-_r_2m0_ .edge-thickness-thick{stroke-width:3.5px;}#chatgpt-mermaid-_r_2m0_ .edge-pattern-solid{stroke-dasharray:0;}#chatgpt-mermaid-_r_2m0_ .edge-thickness-invisible{stroke-width:0;fill:none;}#chatgpt-mermaid-_r_2m0_ .edge-pattern-dashed{stroke-dasharray:3;}#chatgpt-mermaid-_r_2m0_ .edge-pattern-dotted{stroke-dasharray:2;}#chatgpt-mermaid-_r_2m0_ .marker{fill:rgb(175, 175, 175);stroke:rgb(175, 175, 175);}#chatgpt-mermaid-_r_2m0_ .marker.cross{stroke:rgb(175, 175, 175);}#chatgpt-mermaid-_r_2m0_ svg{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;}#chatgpt-mermaid-_r_2m0_ p{margin:0;}#chatgpt-mermaid-_r_2m0_ .label{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";color:rgb(237, 237, 237);}#chatgpt-mermaid-_r_2m0_ .cluster-label text{fill:rgb(237, 237, 237);}#chatgpt-mermaid-_r_2m0_ .cluster-label span{color:rgb(237, 237, 237);}#chatgpt-mermaid-_r_2m0_ .cluster-label span p{background-color:transparent;}#chatgpt-mermaid-_r_2m0_ .label text,#chatgpt-mermaid-_r_2m0_ span{fill:rgb(237, 237, 237);color:rgb(237, 237, 237);}#chatgpt-mermaid-_r_2m0_ .node rect,#chatgpt-mermaid-_r_2m0_ .node circle,#chatgpt-mermaid-_r_2m0_ .node ellipse,#chatgpt-mermaid-_r_2m0_ .node polygon,#chatgpt-mermaid-_r_2m0_ .node path{fill:rgb(9, 23, 44);stroke:rgb(31, 78, 148);stroke-width:1px;}#chatgpt-mermaid-_r_2m0_ .rough-node .label text,#chatgpt-mermaid-_r_2m0_ .node .label text,#chatgpt-mermaid-_r_2m0_ .image-shape .label,#chatgpt-mermaid-_r_2m0_ .icon-shape .label{text-anchor:middle;}#chatgpt-mermaid-_r_2m0_ .node .katex path{fill:#000;stroke:#000;stroke-width:1px;}#chatgpt-mermaid-_r_2m0_ .rough-node .label,#chatgpt-mermaid-_r_2m0_ .node .label,#chatgpt-mermaid-_r_2m0_ .image-shape .label,#chatgpt-mermaid-_r_2m0_ .icon-shape .label{text-align:center;}#chatgpt-mermaid-_r_2m0_ .node.clickable{cursor:pointer;}#chatgpt-mermaid-_r_2m0_ .root .anchor path{fill:rgb(175, 175, 175)!important;stroke-width:0;stroke:rgb(175, 175, 175);}#chatgpt-mermaid-_r_2m0_ .arrowheadPath{fill:rgb(175, 175, 175);}#chatgpt-mermaid-_r_2m0_ .edgePath .path{stroke:rgb(175, 175, 175);stroke-width:1px;}#chatgpt-mermaid-_r_2m0_ .flowchart-link{stroke:rgb(175, 175, 175);fill:none;}#chatgpt-mermaid-_r_2m0_ .edgeLabel{background-color:rgb(0, 0, 0);text-align:center;}#chatgpt-mermaid-_r_2m0_ .edgeLabel p{background-color:rgb(0, 0, 0);}#chatgpt-mermaid-_r_2m0_ .edgeLabel rect{opacity:0.5;background-color:rgb(0, 0, 0);fill:rgb(0, 0, 0);}#chatgpt-mermaid-_r_2m0_ .labelBkg{background-color:rgba(0, 0, 0, 0.5);}#chatgpt-mermaid-_r_2m0_ .cluster rect{fill:rgb(48, 48, 48);stroke:rgba(255, 255, 255, 0.15);stroke-width:1px;}#chatgpt-mermaid-_r_2m0_ .cluster text{fill:rgb(237, 237, 237);}#chatgpt-mermaid-_r_2m0_ .cluster span{color:rgb(237, 237, 237);}#chatgpt-mermaid-_r_2m0_ div.mermaidTooltip{position:absolute;text-align:center;max-width:200px;padding:2px;font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:12px;background:rgb(48, 48, 48);border:1px solid rgba(255, 255, 255, 0.15);border-radius:2px;pointer-events:none;z-index:100;}#chatgpt-mermaid-_r_2m0_ .flowchartTitleText{text-anchor:middle;font-size:18px;fill:rgb(237, 237, 237);}#chatgpt-mermaid-_r_2m0_ rect.text{fill:none;stroke-width:0;}#chatgpt-mermaid-_r_2m0_ .icon-shape,#chatgpt-mermaid-_r_2m0_ .image-shape{background-color:rgb(0, 0, 0);text-align:center;}#chatgpt-mermaid-_r_2m0_ .icon-shape p,#chatgpt-mermaid-_r_2m0_ .image-shape p{background-color:rgb(0, 0, 0);padding:2px;}#chatgpt-mermaid-_r_2m0_ .icon-shape .label rect,#chatgpt-mermaid-_r_2m0_ .image-shape .label rect{opacity:0.5;background-color:rgb(0, 0, 0);fill:rgb(0, 0, 0);}#chatgpt-mermaid-_r_2m0_ .label-icon{display:inline-block;height:1em;overflow:visible;vertical-align:-0.125em;}#chatgpt-mermaid-_r_2m0_ .node .label-icon path{fill:currentColor;stroke:revert;stroke-width:revert;}#chatgpt-mermaid-_r_2m0_ .node .neo-node{stroke:rgb(31, 78, 148);}#chatgpt-mermaid-_r_2m0_ [data-look="neo"].node rect,#chatgpt-mermaid-_r_2m0_ [data-look="neo"].cluster rect,#chatgpt-mermaid-_r_2m0_ [data-look="neo"].node polygon{stroke:url(#chatgpt-mermaid-_r_2m0_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-_r_2m0_ [data-look="neo"].swimlane.cluster rect{filter:none;}#chatgpt-mermaid-_r_2m0_ [data-look="neo"].node path{stroke:url(#chatgpt-mermaid-_r_2m0_-gradient);stroke-width:1px;}#chatgpt-mermaid-_r_2m0_ [data-look="neo"].node .outer-path{filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-_r_2m0_ [data-look="neo"].node .neo-line path{stroke:rgb(31, 78, 148);filter:none;}#chatgpt-mermaid-_r_2m0_ [data-look="neo"].node circle{stroke:url(#chatgpt-mermaid-_r_2m0_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-_r_2m0_ [data-look="neo"].node circle .state-start{fill:#000000;}#chatgpt-mermaid-_r_2m0_ [data-look="neo"].icon-shape .icon{fill:url(#chatgpt-mermaid-_r_2m0_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-_r_2m0_ [data-look="neo"].icon-shape .icon-neo path{stroke:url(#chatgpt-mermaid-_r_2m0_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-_r_2m0_ .node text{font-size:14px;font-weight:600;letter-spacing:normal;fill:rgb(153, 206, 255);}#chatgpt-mermaid-_r_2m0_ .edgeLabels text{font-size:13px;font-weight:600;letter-spacing:-0.08px;fill:rgb(153, 206, 255);}#chatgpt-mermaid-_r_2m0_ .node tspan[font-weight="normal"],#chatgpt-mermaid-_r_2m0_ .edgeLabels tspan[font-weight="normal"]{font-weight:600;}#chatgpt-mermaid-_r_2m0_ .edgeLabel .label rect{opacity:1;rx:13px;ry:13px;fill:rgb(0, 14, 26);stroke:rgb(26, 62, 95);stroke-width:1px;}#chatgpt-mermaid-_r_2m0_ .node rect,#chatgpt-mermaid-_r_2m0_ .node circle,#chatgpt-mermaid-_r_2m0_ .node ellipse,#chatgpt-mermaid-_r_2m0_ .node polygon,#chatgpt-mermaid-_r_2m0_ .node path{fill:rgb(0, 40, 77);stroke:rgba(255, 255, 255, 0.1);stroke-width:1px;}#chatgpt-mermaid-_r_2m0_ .node rect{rx:16px;ry:16px;}#chatgpt-mermaid-_r_2m0_ .node.mermaid-decision .label-container{fill:rgb(0, 14, 26);stroke:rgb(26, 62, 95);stroke-dasharray:2,2;}#chatgpt-mermaid-_r_2m0_ .edgePaths .flowchart-link{stroke:rgb(175, 175, 175);stroke-width:1px;stroke-linecap:round;stroke-linejoin:round;}#chatgpt-mermaid-_r_2m0_ .marker{fill:rgb(175, 175, 175);stroke:rgb(175, 175, 175);}#chatgpt-mermaid-_r_2m0_ :root{--mermaid-font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";}DeveloperGitHub Pull RequestGitHub ActionsTests + Trivy + Dependency +Secret ScansGitHub Workload IdentityFederationTerraform Plan / ApprovedApplyGCP InfrastructureBuild Immutable Docker ImageArtifact RegistryApproved GitOps ChangeImage Digest + Helm ValuesArgo CDHelm ReleaseGKE Autopilot WorkloadsHealth Checks + Smoke Tests





Ownership rules
Owner	Manages
Terraform	VPC, GKE cluster, Cloud SQL, Redis, Pub/Sub, Cloud Storage, IAM, KMS, Secret Manager configuration, Artifact Registry, DNS and approved certificate resources
GKE Gateway controller	Load-balancer resources generated from Gateway API configuration
Argo CD + Helm	Kubernetes deployments, services, ConfigMaps, policies, routes and application configuration
GitHub Actions	Testing, scanning, image building, publishing and controlled promotion requests
GitHub repositories	Application source, Terraform modules, Helm charts and GitOps configuration

Use a versioned, IAM-restricted Cloud Storage bucket for Terraform state, separate from the bucket containing RAG documents. Never put actual credentials in GitHub, image layers or Terraform state.

For GKE, the Gateway API controller can create load-balancer resources, so Terraform and Kubernetes controllers must not independently manage the same forwarding rules, backends or URL maps. 

Google Cloud Documentation
+1




Promotion rule: GitHub Actions may build and publish an image, but production deployment should occur only after an approved GitOps change. Argo CD then pulls that configuration and deploys the approved image digest.
6. Pending edge cases and how to resolve them
These are the most important issues to close before calling the platform production-ready.
Priority	Edge case	Required solution
Critical	Development, staging and production share one cluster	Use separate namespaces, identities, secrets, quotas and network controls initially. Decide whether production requires a separate GCP project and cluster for stronger isolation. A single shared cluster remains a common failure domain.
Critical	Cross-tenant data leakage	Enforce server-derived tenant context, database authorization/RLS where applicable, tenant-filtered vector retrieval and authorization tests for every endpoint and tool.
Critical	Worker restarts or duplicate Pub/Sub messages	Persist workflow state, use idempotency keys, record action receipts, configure dead-letter topics and reconcile external state before retrying writes.
Critical	Unauthorized or unsafe remediation	Use OPA/Rego, constrained MCP tools, least-privilege credentials, approval expiry and immediate pre-execution policy checks. Fail closed when authorization or policy evaluation is unavailable.
Critical	Secrets exposed through images, logs or pipelines	Use Secret Manager, workload identity, restricted CI permissions, secret scanning and log redaction. Never rely on long-lived service-account key files.
High	Cloud SQL or Keycloak outage	Configure database HA and backups, run multiple application replicas where appropriate, test recovery, and fail closed for new privileged actions if durable state is unavailable.
High	Model quota exhaustion or Vertex AI outage	Apply bounded retries, per-tenant budgets and approved fallback model profiles. Otherwise return partial findings or defer the workflow without performing unsafe actions.
High	RAG contains stale or unauthorized documents	Maintain document versions, ACLs, source provenance and deletion workflows. Use live provider APIs to verify current resource state.
High	Kubernetes pods exceed available resources	Set CPU/memory requests and limits, probe endpoints, define autoscaling behavior and test GKE Autopilot scheduling constraints.
High	Policy or approval changes while a request is pending	Bind approval to the exact action and target, expire it, and revalidate the current policy and resource state before execution.
High	Database or model cost grows unexpectedly	Add per-tenant quotas, model/token budgets, connection-pool limits, retention policies and budget alerts.
High	Publicly exposed admin endpoints	Keep Kong admin interfaces and Argo CD administration private; tightly restrict Keycloak administration and production deployment permissions.
Medium	Certificate or DNS cutover fails	Verify certificate provisioning, DNS records, load-balancer health and rollback instructions before moving production traffic.
Medium	Observability outage or sensitive telemetry	Use bounded telemetry buffering, structured redaction, retention limits and monitoring-backend failure alerts. Durable business audits must not rely solely on telemetry export.
Medium	Integration permissions expire or drift	Add health checks, permission validation, rotation, reauthorization and revocation workflows.
Medium	GCP inventory results are stale	Use Cloud Asset Inventory for discovery and historical metadata, then query live APIs before high-impact operational decisions.

Pub/Sub retry and dead-letter configuration is particularly important because failed messages can be delivered again, and a worker must not assume that each delivery represents a new business operation. 

Google Cloud Documentation


What the client should receive as a completed project
The deliverable is more than a running website. It should include:
- Architecture diagram and approved component inventory.
- Terraform-managed infrastructure and secured remote state.
- Helm charts and Argo CD GitOps configuration.
- CI/CD pipelines with testing and security scanning.
- Keycloak authentication and tenant-level authorization.
- Working agent workflows, RAG retrieval and Vertex AI integration.
- Constrained MCP tools with policy enforcement and human approvals.
- Cloud SQL persistence, Pub/Sub retries and recovery behavior.
- OpenTelemetry instrumentation, dashboards, SLOs and alerts.
- Backup/restore procedures, incident runbooks and documented rollback.
- Evidence of security, integration, load and failure-recovery testing.
Final client-facing explanation
We are building a multi-tenant AI operations platform on Google Cloud using GKE Autopilot. Google Cloud manages the application infrastructure and data services, while specialist AI agents investigate operational problems and recommend or execute approved actions.

Cloud DNS, the global load balancer and Cloud Armor provide secure external access. Kong centralizes API and AI traffic, Keycloak manages authentication, and FastAPI enforces application authorization. LangGraph coordinates the agents, Vertex AI supplies model inference, PostgreSQL with pgvector provides durable application state and retrieval, and Pub/Sub supports asynchronous workflows.

OPA/Rego, human approvals and the MCP execution boundary prevent AI-generated recommendations from becoming unauthorized infrastructure changes. OpenTelemetry and Google Cloud observability services provide operational visibility. Finally, Terraform, GitHub Actions, Artifact Registry, Helm and Argo CD deliver repeatable, version-controlled infrastructure and application releases.

The remaining production gates are tenant-isolation validation, safe remediation, recovery testing, regional disaster-recovery decisions, and verification of the actual deployed infrastructure.

Bottom line: use the resources above as one coherent architecture, not as separate services that each try to perform the same function. The biggest outstanding risk is not a missing AI component; it is whether tenant isolation, durable execution, privileged-action safety and disaster recovery have been implemented and tested end to end.




The seven controls I would implement
1. Tenant identity: Every request must resolve to a verified organization and tenant ID from the authenticated identity and server-side authorization context. Never trust a tenant ID supplied only in a request body or URL.
2. Application authorization: FastAPI checks organization, project, environment and resource permissions. Use your RBAC/ABAC model and OPA/Rego where appropriate.
3. Kubernetes isolation: Create namespaces, namespace-scoped RBAC, default-deny NetworkPolicies, resource quotas, admission policies and dedicated workload identities. Avoid giving tenant users cluster-wide administrative access. 
   
   Google Cloud Documentation
   +1
4. Database isolation: For standard tenants, PostgreSQL can use tenant-scoped tables, enforced row-level security and least-privilege database roles. Use separate databases or instances when contractual or risk requirements demand stronger separation.
5. RAG isolation: Apply tenant and document ACL filters on every retrieval. A vector search must not return another tenant's documents, chunks, metadata or cached results. Consider separate indexes or storage for high-security tenants.
6. Agent isolation: Every LangGraph execution, tool call, MCP request and remediation action must inherit the authorized tenant context. Validate permissions again before sensitive actions; do not rely solely on the LLM to enforce security.
7. Audit and cost: Record tenant ID, actor, agent, tool, resource, decision and trace ID in audit events. Apply per-tenant rate limits, token budgets and concurrency limits to prevent noisy neighbors and uncontrolled AI spending.