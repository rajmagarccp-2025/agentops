# GCP infrastructure with OpenTofu

This module provisions the GKE Autopilot foundation and GCP services for AgentOps.
The GitHub Actions workflow bootstraps the dedicated OpenTofu state bucket before
initializing the remote GCS backend.

## Required inputs

- `project_id`: the Google Cloud project hosting the platform
- `database_password`: secure Postgres password for the Cloud SQL instance

## Remote state

OpenTofu stores state in `gs://project-cks-aug2026-agentops-tofu-state` under
`agentops/prod/default.tfstate`. GCS state locking and bucket object versioning
are enabled. The deployment workflow creates the bucket once with uniform
bucket-level access and public access prevention before running `tofu init`.
Keep access to this bucket restricted: Terraform state contains sensitive
infrastructure data, including the Cloud SQL password.

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

## GitHub Actions identity bootstrap

Use a dedicated GitHub deployer service account, separate from the runtime
`agentops-platform-sa-gcp` service account. Create it and bind the repository's
Workload Identity principal (project number `964665867515`):

```bash
gcloud iam service-accounts create agentops-github-deployer \
  --project=project-cks-aug2026 \
  --display-name="AgentOps GitHub Actions Deployer"

gcloud iam service-accounts add-iam-policy-binding \
  agentops-github-deployer@project-cks-aug2026.iam.gserviceaccount.com \
  --project=project-cks-aug2026 \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/964665867515/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/rajmagarccp-2025/agentops"
```

For the initial provisioning workflow, grant the deployer these predefined
roles (then replace broad service-admin roles with a reviewed custom role when
you have validated the full resource set):

```bash
DEPLOYER="serviceAccount:agentops-github-deployer@project-cks-aug2026.iam.gserviceaccount.com"
for ROLE in \
  roles/serviceusage.serviceUsageAdmin \
  roles/storage.admin \
  roles/compute.networkAdmin \
  roles/servicenetworking.networksAdmin \
  roles/container.admin \
  roles/artifactregistry.admin \
  roles/cloudsql.admin \
  roles/redis.admin \
  roles/iam.serviceAccountAdmin \
  roles/iam.serviceAccountUser \
  roles/resourcemanager.projectIamAdmin \
  roles/pubsub.admin \
  roles/secretmanager.admin \
  roles/cloudkms.admin
do
  gcloud projects add-iam-policy-binding project-cks-aug2026 \
    --member="$DEPLOYER" \
    --role="$ROLE"
done
```

Do not grant `roles/owner`. `roles/storage.admin` is needed for the first-run
state bucket bootstrap and the GCS backend; restrict state bucket access after
provisioning if you narrow the deployer's project-wide permissions.

Configure these GitHub environment secrets under **Settings → Environments →
prod**:

- `GCP_WORKLOAD_IDENTITY_PROVIDER`:
  `projects/964665867515/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider`
- `GCP_SERVICE_ACCOUNT`:
  `agentops-github-deployer@project-cks-aug2026.iam.gserviceaccount.com`
- `TF_DATABASE_PASSWORD`: strong unique database password
- `JWT_DEMO_SECRET`: random secret of at least 32 bytes
- `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`: values from the
  production Keycloak client

The selected repository and branch must also satisfy the Workload Identity
provider's attribute condition. The deployer service account is not the
Kubernetes runtime service account.

The prod configuration creates billable resources, including an Autopilot
cluster, regional production Cloud SQL, and HA Redis. Review the OpenTofu plan
and expected GCP charges before the first automatic apply.

## Example usage

```bash
cd infrastructure/terraform/gcp
tofu init
tofu plan \
  -var="project_id=project-cks-aug2026" \
  -var="project_name=agentops-platform" \
  -var="environment=prod" \
  -var="region=us-central1" \
  -var="namespace=prod" \
  -var="service_account_name=agentops-platform-sa-gcp"
```

## Provisioned resources

- GKE Autopilot cluster
- VPC and subnet with secondary ranges for Pods and Services
- Private Service Networking for Cloud SQL and Redis access
- Artifact Registry repository
- GCS application-artifact bucket with uniform access, public access prevention,
  and object versioning
- Pub/Sub event topic, subscription, and dead-letter topic
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
- The remote state bucket is bootstrap infrastructure managed by the workflow's
  idempotent `gcloud storage` step and is intentionally separate from the
  application artifact bucket managed by OpenTofu.
- This module provisions the GCP service foundation and IAM only. The current
  application does not yet contain production GCP adapters for GCS, Pub/Sub,
  Secret Manager, KMS, or Vertex AI; adding those client integrations and
  end-to-end adapter tests remains separate application work.
- For production, protect the state bucket and restrict the GitHub deploy
  service account to the required state, infrastructure, registry, and GKE
  permissions.
