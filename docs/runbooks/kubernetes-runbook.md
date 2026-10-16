# Kubernetes Runbook

## Inspect

```text
kubectl config current-context
kubectl get nodes
kubectl -n agentic-platform get pods,svc,ingress,hpa,pdb
kubectl -n agentic-platform get events --sort-by=.lastTimestamp
```

## Render before apply

```text
kubectl kustomize deployment/kubernetes/base
kubectl kustomize deployment/kubernetes/overlays/dev
kubectl kustomize deployment/kubernetes/overlays/staging
kubectl kustomize deployment/kubernetes/overlays/prod
```

## Common recovery

- Pending pod: inspect scheduling events, resource requests, and node capacity.
- CrashLoopBackOff: inspect logs and `/api/v1/health` startup behavior.
- Readiness failure: check PostgreSQL and Redis connectivity.
- Ingress failure: inspect nginx controller, TLS secret, cert-manager, and DNS.
- Network failure: inspect NetworkPolicies before opening broader access.

Do not bypass security contexts, NetworkPolicies, or secret-manager controls during
an incident without an approved emergency change.
