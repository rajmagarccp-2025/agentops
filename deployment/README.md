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

The API exposes `/api/v1/health`, `/api/v1/health/ready`, and `/api/v1/metrics`
for probes and scraping. The API and web Deployments use non-root security
contexts, read-only filesystems, resource limits, disruption budgets, and network
policies.
