# Cluster bootstrap guide

This bootstrap flow is designed for an existing Kubernetes cluster and assumes the platform repository is already checked out locally.

## Preconditions

- `kubectl` installed and configured to the target cluster
- access to a working Kubernetes context
- a secret manager endpoint such as HashiCorp Vault or a compatible alternative
- the `ingress-nginx` controller and `cert-manager` CRDs installed, or the repo manifests applied before the app deployment

## Bootstrap steps

1. Validate cluster access
   ```bash
   kubectl cluster-info
   kubectl get nodes
   ```
2. Install Argo CD and the platform namespaces
   ```bash
   bash deployment/bootstrap/cluster-install.sh
   ```
3. Verify Argo CD is healthy
   ```bash
   kubectl -n argocd get pods
   kubectl -n argocd get svc
   ```
4. Confirm the platform namespace is ready
   ```bash
   kubectl -n agentic-platform get pods
   ```
5. Validate configured secrets are synced from the external secret store
   ```bash
   kubectl -n agentic-platform get secret platform-secrets
   ```
6. Apply the GitOps app definitions as the final repo sync layer
   ```bash
   kubectl apply -f deployment/argocd/projects/platform-project.yaml
   kubectl apply -f deployment/argocd/applications/platform-api.yaml
   kubectl apply -f deployment/argocd/applications/platform-web.yaml
   kubectl apply -f deployment/argocd/applications/release-orchestrator.yaml
   ```

## Security notes

- Do not commit real secrets or password values.
- Replace example Vault URLs and token values before production use.
- Prefer external secret injection from a real secret manager, not from repository YAML.
- For production, rotate the Argo CD admin password and replace the sample value in the bootstrap manifest.
