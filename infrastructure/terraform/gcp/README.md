# GCP infrastructure with OpenTofu

This module provisions the GKE Autopilot foundation and GCP services for AgentOps.
The GitHub Actions workflow verifies the existing OpenTofu state bucket before
initializing the remote GCS backend. It never creates or replaces the state bucket.

## Required inputs

- `project_id`: approved Google Cloud project ID
- `project_name`: approved resource-name prefix
- `environment`: approved deployment environment (`dev`, `staging`, or `prod`)
- `region`: approved Google Cloud region
- `namespace`: Kubernetes namespace bound to Workload Identity
- `service_account_name`: GCP runtime service account ID
- `database_password`: secure Postgres password for the Cloud SQL instance; provide
  through the protected GitHub environment secret `TF_DATABASE_PASSWORD` as
  `TF_VAR_database_password`, never through a committed tfvars file.

The deployment workflow requires an approved hostname as the `GCP_DOMAIN`
GitHub environment variable for configuration checks. The Terraform module
contains opt-in resources for a global static IP, Cloud Armor, Cloud DNS
authorization/records, a Google-managed certificate, and a Certificate
Manager map. These resources are disabled by default. DNS changes require an
explicit review of the production plan and an existing Cloud DNS zone owned by
this project.

To include the public edge in a reviewed plan, provide all of the following
through approved environment variables or a protected CI environment:

- `TF_VAR_enable_public_edge=true`
- `TF_VAR_enable_public_dns_record=true`
- `TF_VAR_public_domain=<approved-hostname>`
- `TF_VAR_dns_managed_zone=<existing-zone-name>`

The DNS flag creates both certificate-authorization records and the hostname A
record. Do not enable it until ownership, staging, TTL, and rollback have been
confirmed. The GKE Gateway chart remains disabled until its `gateway.*` values
are set from the outputs `public_edge_ip_name`,
`public_edge_cloud_armor_policy_name`, and `public_edge_certificate_map`.
SQL-injection and XSS WAF rules are initially in preview; the per-IP Cloud
Armor throttle is enforced. Terraform code and a rendered chart are not proof
of a live TLS certificate or healthy Gateway.

## Remote state

OpenTofu stores state in `gs://project-cks-aug2026-agentops-tofu-state` under
`agentops/prod/default.tfstate`. GCS state locking and bucket object versioning
are expected, as are uniform bucket-level access and public access prevention.
The deployment workflow verifies these settings and fails if the existing
bucket is missing or does not meet them. It does not create, rename, or replace
the bucket, and it verifies the expected state object exists before initializing
the backend. If the bucket or object is missing, stop and investigate; do not
initialize a new empty state at another location. Keep access to this bucket
restricted: Terraform state contains sensitive infrastructure data, including
the Cloud SQL password. Do not change
the backend bucket or prefix without a reviewed state migration and explicit
approval; never initialize a new empty backend or use `-backend=false` for
normal plans or applies.

For local state inspection or drift checks, authenticate with an identity that
has access to the state bucket, then run:

```bash
cd infrastructure/terraform/gcp
tofu init
tofu plan -refresh-only
tofu plan
```

Do not use `tofu init -backend=false` for normal plans or applies; it bypasses
the shared state.

## GitHub Actions identity and configuration

Use GitHub Workload Identity Federation with a dedicated deployer service
account, separate from the Kubernetes runtime service account. Do not create or
use service-account key files. Bind only the intended repository and protected
branch/environment in the Workload Identity provider condition:

```bash
gcloud iam service-accounts create "$DEPLOYER_SERVICE_ACCOUNT_NAME" \
  --project="$APPROVED_PROJECT_ID" \
  --display-name="AgentOps GitHub Actions Deployer"

gcloud iam service-accounts add-iam-policy-binding \
  "$DEPLOYER_SERVICE_ACCOUNT_NAME@$APPROVED_PROJECT_ID.iam.gserviceaccount.com" \
  --project="$APPROVED_PROJECT_ID" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$WORKLOAD_IDENTITY_PROJECT_NUMBER/locations/global/workloadIdentityPools/$WORKLOAD_IDENTITY_POOL/attribute.repository/$GITHUB_REPOSITORY"
```

The previously documented bootstrap role set contains broad project-level
permissions. Do not grant that set as a bundle. Review the deployer's actual
required permissions and resource scope before provisioning:

| Existing/documented role | Risk / proposed narrower approach |
|---|---|
| `roles/resourcemanager.projectIamAdmin` | Very broad project IAM mutation. Replace with reviewed, resource-scoped bindings and a narrowly scoped custom role only if IAM binding changes are required. |
| `roles/iam.serviceAccountAdmin` | Can administer service accounts. Limit management to the specific runtime/deployer accounts and required create/update permissions. |
| `roles/iam.serviceAccountUser` | Allows acting as service accounts. Grant only on the exact service accounts the workflow must impersonate. |
| `roles/storage.admin` | Broad bucket/object administration. Separate state-bucket access from application resources; use bucket-scoped backend permissions and narrowly scoped artifact-bucket permissions. |
| `roles/compute.networkAdmin`, `roles/servicenetworking.networksAdmin` | Broad network/peering control. Scope to the platform network and required address/connection operations using a reviewed custom role. |
| `roles/container.admin` | Broad cluster administration. Restrict to the named cluster and required provisioning/deployment operations. |
| `roles/artifactregistry.admin` | Broad registry administration. Scope writer/reader access to the named repository. |
| `roles/cloudsql.admin`, `roles/redis.admin` | Broad database/cache administration. Use resource-scoped permissions/custom roles for only the declared instance operations. |
| `roles/pubsub.admin`, `roles/secretmanager.admin`, `roles/cloudkms.admin` | Broad service administration. Scope topic, secret, and key access to the named resources and required operations. |
| `roles/serviceusage.serviceUsageAdmin` | Can enable/disable services. Limit API enablement to the declared API set and provisioning identity. |

These are recommendations, not IAM changes. No roles are silently removed or
replaced here; inspect current bindings and validate a least-privilege
replacement against the deployment before changing access. Do not grant
`roles/owner`.

Configure the `prod` GitHub environment with required reviewers and restrict
deployment branches. Set these **Actions variables** to owner-approved values:

- `GCP_PROJECT_ID`, `GCP_PROJECT_NAME`, `GCP_REGION`, `GCP_ENVIRONMENT`
- `GCP_NAMESPACE`, `GCP_RUNTIME_SERVICE_ACCOUNT`, `GCP_DOMAIN`
- `GCP_CLUSTER_NAME`, `GCP_REPOSITORY`

Set these **Actions secrets** without printing their values:

- `GCP_WORKLOAD_IDENTITY_PROVIDER`: approved Workload Identity provider resource
- `GCP_SERVICE_ACCOUNT`: dedicated GitHub deployer service-account email
- `TF_DATABASE_PASSWORD`: unique database password
- `JWT_DEMO_SECRET`: random secret of at least 32 bytes
- `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`: approved OIDC client
  configuration

The runtime service account and GitHub deployer are separate identities. The
workflow runs quality checks on pushes, but infrastructure planning is manual
and review-only; this workflow contains no infrastructure apply. Application
deployment is separately opt-in and still depends on a successful plan. Review
the plan and expected GCP charges before approving any later, separately
implemented apply path.

Enable GitHub secret scanning and push protection for the repository before
using deployment credentials. Review staged changes and workflow logs for
credential exposure; never place secret values in Terraform arguments, example
tfvars, generated artifacts, or diagnostic output.

## Example usage

```bash
cd infrastructure/terraform/gcp
tofu init
tofu plan \
  -var="project_id=<approved-project-id>" \
  -var="project_name=<approved-resource-prefix>" \
  -var="environment=<approved-environment>" \
  -var="region=<approved-region>" \
  -var="namespace=<approved-namespace>" \
  -var="service_account_name=<approved-runtime-service-account>"
```

Supply `database_password` through `TF_VAR_database_password` from a protected
secret; do not put it in a command-line argument or a committed tfvars file.
Use the existing remote backend shown above.

## Provisioned resources

- GKE Autopilot cluster
- VPC and subnet with secondary ranges for Pods and Services
- Private Service Networking for Cloud SQL and Redis access
- Artifact Registry repository
- GCS application-artifact bucket with uniform access, public access prevention,
  and object versioning
- Pub/Sub event topic, subscription, and dead-letter topic
- Dedicated operator subscription for inspecting dead-letter messages
- Secret Manager secret containers for database, Redis, JWT, and OIDC runtime
  settings (the deploy workflow publishes secret versions)
- Cloud KMS key for application encryption integrations
- Cloud SQL for PostgreSQL; enable pgvector in the application database with
  `CREATE EXTENSION IF NOT EXISTS vector;`
- Memorystore Redis instance
- Workload Identity service account binding
- Runtime IAM bindings for Vertex AI, Pub/Sub, GCS, Secret Manager, KMS,
  Cloud Logging, Monitoring, and Trace
- Required GCP APIs

## Notes

- The deployment keeps provider-specific resources isolated under `infrastructure/terraform/gcp`.
- Workload Identity binds the Kubernetes service account to the GCP service account using the `namespace` and `service_account_name` variables.
- Private networking is enabled for Cloud SQL and Redis so the app runs inside the VPC rather than exposing public database endpoints.
- Cloud SQL uses the `ALWAYS` activation policy so it is running when OpenTofu manages its database and user. Manually stopping it is drift; the next apply will start it again, and the instance continues to incur compute charges while running.
- The remote state bucket and state object are pre-existing shared state
  infrastructure. The workflow verifies them but does not create, update, or
  manage them; the application artifact bucket is a separate OpenTofu resource.
- This module provisions the GCP service foundation and IAM only. The current
  application has a GCS adapter for archiving original RAG documents. The
  document archive bucket is external and is not provisioned by this module.
  Before deployment, configure the GitHub environment variable
  `GCS_DOCUMENT_BUCKET` with its bucket name and grant the GKE runtime service
  account bucket-scoped `roles/storage.objectUser` access. Confirm the
  Kubernetes-to-Google service account Workload Identity binding and bucket
  permissions separately; no service-account key files are used. This module
  provides Secret Manager access only to the six pre-provisioned bootstrap
  secrets. The backend has a runtime Secret Manager adapter; set
  `GCP_SECRET_MANAGER_PROJECT_ID` through the GCP Helm deployment. For each
  application-managed secret, pre-provision its tenant/scope-scoped resource
  with the expected AgentOps ownership labels and grant the runtime service
  account `roles/secretmanager.secretAccessor`,
  `roles/secretmanager.secretVersionAdder`, and
  `roles/secretmanager.secretVersionManager` on that secret only. The workflow
  seeds bootstrap values into Secret Manager only when no version exists, then
  projects Secret Manager's latest versions into the Kubernetes Secret during
  deployment. It does not install External Secrets Operator or enable automatic
  rotation. No project-wide Secret Manager administrator role is granted.
  The separate GitHub deploy identity needs resource-scoped version-list,
  version-access, and initial-version-add permissions on the six bootstrap
  secrets for that sync. The workflow worker uses Workload Identity with
  publisher access to the events topic and subscriber access to the events
  subscription. The Pub/Sub service agent is granted subscriber access to that
  subscription and publisher access to the dead-letter topic, as required for
  dead-letter routing. The runtime identity does not receive access to the
  operator dead-letter subscription. The workflow deploy step derives topic and
  subscription IDs from `GCP_PROJECT_NAME` and `GCP_ENVIRONMENT`; these must
  match the Terraform resource prefix and environment. The backend uses a
  transactional PostgreSQL outbox and the database remains authoritative.
  Pub/Sub delivery, IAM, and DLQ routing still require verification in an
  approved non-production GCP project before production rollout. KMS and Vertex
  AI runtime adapters remain incomplete.
- Terraform does not currently provision Keycloak, Kong Gateway, public DNS,
  or TLS certificates. The GCP Helm values intentionally leave ingress disabled;
  production DNS, the approved gateway, certificates, and Keycloak realm/client
  bootstrap must be automated before the platform is publicly reachable.
- Application rollout is opt-in in the GCP workflow and checks the configured
  OIDC issuer's HTTPS discovery endpoint. This prevents rollout with a local or
  unreachable issuer but does not provision the identity provider itself.
- For production, protect the state bucket and restrict the GitHub deploy
  service account to the required state, infrastructure, registry, and GKE
  permissions.
