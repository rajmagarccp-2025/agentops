# Deployment Runbook

## Preflight

```text
make lint
make typecheck
make test
kubectl kustomize deployment/kubernetes/overlays/staging
kubectl kustomize deployment/kubernetes/overlays/prod
```

Confirm secrets are externalized, migration SQL is reviewed, image tags are
immutable, and the release baseline identifies the intended revision.

## GitOps deployment

Apply or update the Argo CD project and application definitions:

```text
kubectl apply -f deployment/argocd/projects/platform-project.yaml
kubectl apply -f deployment/argocd/applications/platform-api.yaml
kubectl apply -f deployment/argocd/applications/platform-web.yaml
kubectl apply -f deployment/argocd/applications/release-orchestrator.yaml
```

Observe synchronization:

```text
kubectl -n argocd get applications
kubectl -n agentic-platform get pods
```

Production requires the promotion approval and release-lock gate.

## Post-deploy

Check health, readiness, metrics, logs, traces, and a representative authenticated
read-only request before declaring success.
