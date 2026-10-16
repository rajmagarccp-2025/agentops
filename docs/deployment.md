# Deployment Guide

## Overview

The platform supports multi-cloud deployment across AWS, Azure, GCP, and Kubernetes using Terraform, Helm, and GitOps via Argo CD.

```text
LOCAL -> DEV -> STAGING -> PRODUCTION
```

## Kubernetes & Helm Deployment

```bash
helm upgrade --install platform deployment/helm/platform \
  --namespace agentic-platform-prod \
  --create-namespace \
  --values deployment/helm/platform/values-gcp.yaml
```

## GitOps via Argo CD

Apply Argo CD application manifests:

```bash
kubectl apply -f deployment/argocd/project.yaml
kubectl apply -f deployment/argocd/application.yaml
```
