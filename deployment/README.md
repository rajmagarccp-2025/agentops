# Deployment

Application deployment assets are separated from cloud provisioning in
`infrastructure/`.

## Phase 18 assets

- `docker/api.Dockerfile` and `docker/web.Dockerfile`: non-root production images
- `kubernetes/`: Kustomize-ready namespace, ConfigMap, Secret template, Deployments,
	Services, probes, HPA, PDB, and NetworkPolicies
- `helm/platform/`: canonical configurable Helm chart for the API, worker, and web topology

## Kubernetes

```text
kubectl apply -k deployment/kubernetes
kubectl -n agentic-platform get pods,svc,hpa,pdb,ingress
```

`secret.example.yaml` is a template only. Replace its values through an external
secret manager or a deployment-time secret process. Do not commit real credentials.

### TLS and external secrets

- `cert-manager/cluster-issuer.yaml`: LetsEncrypt cluster issuer for nginx ingress
- `secrets/secret-store.yaml`: Vault-backed `ClusterSecretStore`
- `secrets/externalsecret.yaml`: syncs secrets into the app namespace
- `secrets/vault-token-secret.yaml`: token secret for the secret-store
- `ingress/ingress.yaml`: HTTP -> HTTPS redirect and TLS route for the platform

Apply cert-manager and external-secrets first, then the platform resources.

## Helm

```text
helm upgrade --install platform deployment/helm/platform \
	--namespace platform-prod --create-namespace \
	--values deployment/helm/platform/values-gcp.yaml
```

## GitHub Actions and GCP deployment

The repository includes a GCP deployment workflow at `.github/workflows/deploy-gcp.yml`.
It uses GitHub OIDC Workload Identity Federation to authenticate to Google Cloud and
publishes the API, worker, and frontend images to Artifact Registry before upgrading the
Helm release on the target GKE cluster.

Required `prod` environment secrets:

- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`
- `TF_DATABASE_PASSWORD`
- `JWT_DEMO_SECRET`
- `OIDC_ISSUER_URL`
- `OIDC_CLIENT_ID`
- `OIDC_CLIENT_SECRET`

Add them as **environment secrets** under **Repository Settings → Environments
→ `prod` → Environment secrets → Add secret**. The workflow targets this
environment, so repository-level secrets or local `.env` files are not a
substitute. Use these values:

| Name | Value |
| --- | --- |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Full Workload Identity Provider resource name from GCP, such as `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID`. |
| `GCP_SERVICE_ACCOUNT` | Service account email that the GitHub Actions workflow is allowed to impersonate. Workload Identity Federation is used; do not create or store a service-account JSON key. |
| `TF_DATABASE_PASSWORD` | Password for the provisioned PostgreSQL user. |
| `JWT_DEMO_SECRET` | A strong, randomly generated signing secret for the application. |
| `OIDC_ISSUER_URL` | Exact HTTPS issuer URL for the production identity provider/realm. It must be reachable by the workflow and users; localhost is rejected. |
| `OIDC_CLIENT_ID` | Client identifier registered with that identity provider. |
| `OIDC_CLIENT_SECRET` | Client secret for that registered client. Treat it as confidential. |

For each entry, select **Add secret**, enter the exact name and value, and save.
Do not put real values in source control, example manifests, screenshots, or
chat. The workflow reads these values from the `prod` environment and publishes
the database URL, JWT secret, and OIDC settings to Google Secret Manager and the
Kubernetes `platform-secrets` Secret during deployment.

The workflow bootstraps a dedicated, versioned GCS bucket for OpenTofu state,
provisions infrastructure, and builds/pushes the images. Application rollout is
opt-in: set the workflow dispatch input `deploy_application` to `true`, or set
the `DEPLOY_APPLICATION` Actions variable to `true` for automatic rollout on
pushes to `main`. With the default setting, infrastructure and images are still
provisioned, but the application is not rolled out.

To check GKE access, scheduling, and Artifact Registry image pulls without
rolling out the application or requiring OIDC runtime secrets, manually run
`.github/workflows/gke-smoke-test.yml` with an existing image tag. It creates a
temporary, private namespace and removes it after the check. This verifies
cluster/image deployment plumbing only; it does not deploy or expose the app,
test its runtime configuration, or replace the OIDC validation required for an
application rollout.

When rollout is enabled, the workflow verifies that `OIDC_ISSUER_URL` uses
HTTPS and that its OpenID Connect discovery document is reachable and reports
the exact configured issuer. A localhost issuer such as
`http://localhost:8080` is rejected.

The current Terraform root does not provision Keycloak or Kong. The GCP Helm
values keep the public Gateway disabled, so successful
application rollout is not the same as making the application publicly
reachable. Configure the production identity provider and supply owner-approved
DNS/TLS values before enabling the public edge. The GCP chart deploys
Kong Gateway OSS as a private ClusterIP edge. Kong owns API routing, per-IP
best-effort edge limits, and request-size limits; the API remains authoritative
for OIDC validation, authorization, tenant scope, and LLM budgets/model routing.
Kong AI Gateway plugins are intentionally not enabled; adding them requires an
approved Kong edition/license and a separate policy-ownership review. The
development-only `deployment/kong/kong.yml` is used by Docker Compose and must
not be deployed to GKE.

### OPA and telemetry

The GCP Helm profile deploys OPA as a private, read-only-policy service. Only
API pods can call its decision endpoint; API mutations fail closed when OPA is
unavailable. The policy checked into `policy/agentops` is packaged in the Helm
chart and a CI check verifies that the packaged policy matches the tested
source. OPA is not a public service and its control endpoints are not exposed
outside the cluster.

The GCP profile also enables an OpenTelemetry Collector. API traces are sent
over cluster-internal OTLP/gRPC, while the Collector scrapes the API metrics
endpoint and exports both signals to Cloud Trace and Cloud Monitoring using
the GKE Workload Identity service account. GKE's managed logging agent collects
the API's structured stdout logs into Cloud Logging. Verify the Cloud IAM
bindings, Collector health, trace/metric arrival, dashboards, and alert routing
in the target project; source configuration alone is not delivery evidence.
`ServiceMonitor` remains disabled because Prometheus Operator installation has
not been confirmed.

### Optional public Gateway

The chart's public GKE Gateway API resources are disabled by default. To
activate them, first review and opt in to Terraform variables
`enable_public_edge=true` and `enable_public_dns_record=true` only for an
approved domain and existing Cloud DNS zone that this project is authorized to
change. Terraform then reserves the global address, creates a Cloud Armor
policy, DNS authorization, Google-managed certificate and certificate map, and
publishes the A/CNAME records. The SQL-injection and XSS WAF rules start in
preview; the IP throttle is enforced. After reviewing the exact plan and
confirming DNS ownership, deploy the chart with
`gateway.enabled=true`, `gateway.domain`, and the corresponding Terraform
outputs `public_edge_ip_name`, `public_edge_cloud_armor_policy_name`, and
`public_edge_certificate_map`. No public edge or DNS change is enabled by the
checked-in default values. Test Gateway health and rollback in a non-production
environment before any production cutover.

See `infrastructure/terraform/gcp/README.md` for remote-state and drift-check
commands.

Set `DEPLOY_APPLICATION` to `true` only after the production Keycloak issuer and
client secrets are configured and the issuer discovery check succeeds.

The bootstrap Argo CD manifest in `deployment/argocd/bootstrap/argocd-install.yaml`
keeps the admin password out of source control; the initial admin password is generated by
Argo CD itself and should be rotated on first login.

The API exposes `/api/v1/health`, `/api/v1/health/ready`, and `/api/v1/metrics`
for probes and scraping. The API and web Deployments use non-root security
contexts, read-only filesystems, resource limits, disruption budgets, and network
policies.
