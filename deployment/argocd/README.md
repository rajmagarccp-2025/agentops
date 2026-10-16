# Argo CD (GitOps)

This directory contains the Argo CD application project and the Helm-based GitOps manifests used to deploy the platform into the target cluster.

## Included manifests

- `project.yaml`: AppProject for the platform environments
- `application.yaml`: single production deployment using Helm values for GCP
- `applicationset.yaml`: environment matrix for dev, staging, and production
- `environments/*.yaml`: concrete environment examples
- `bootstrap/`: bootstrap installation manifest for the Argo CD control plane

## Required update before apply

Replace the placeholder repository URL with the actual GitHub repository that hosts this platform before applying the manifests:

```yaml
source:
  repoURL: https://github.com/<your-org>/<your-repo>.git
```

## Apply order

1. Install Argo CD using `deployment/argocd/bootstrap/argocd-install.yaml`
2. Apply `deployment/argocd/project.yaml`
3. Apply `deployment/argocd/application.yaml` or `deployment/argocd/applicationset.yaml`

This repository deploys the Helm chart from `deployment/helm/platform` with the GCP values file selected by default for the target environment.
