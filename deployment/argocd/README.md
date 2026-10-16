# Argo CD (GitOps)

This directory contains the Argo CD application project and the Helm-based GitOps manifests used to deploy the platform into the target cluster.

## Included manifests

- `project.yaml`: AppProject for the platform environments
- `application.yaml`: single production deployment using Helm values for GCP
- `applicationset.yaml`: environment matrix for dev, staging, and production
- `environments/*.yaml`: concrete environment examples
- `bootstrap/`: bootstrap installation manifest for the Argo CD control plane

## Repository

The current production Application points at
`https://github.com/rajmagarccp-2025/agentops.git`. Update it if the repository
is renamed or moved.

## Apply order

1. Install Argo CD using `deployment/argocd/bootstrap/argocd-install.yaml`
2. Apply `deployment/argocd/project.yaml`
3. Apply `deployment/argocd/application.yaml` or `deployment/argocd/applicationset.yaml`

This repository deploys the Helm chart from `deployment/helm/platform` with the GCP values file selected by default for the target environment.
