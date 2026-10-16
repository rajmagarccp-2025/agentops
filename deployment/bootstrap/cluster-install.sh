#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_NAMESPACE="agentic-platform"
ARGOCD_NAMESPACE="argocd"
EXTERNAL_SECRETS_NAMESPACE="external-secrets"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required but not installed." >&2
  exit 1
fi

kubectl create namespace "$ARGOCD_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace "$TARGET_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace "$EXTERNAL_SECRETS_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f "$REPO_ROOT/deployment/argocd/bootstrap/argocd-install.yaml"
kubectl apply -f "$REPO_ROOT/deployment/kubernetes/cert-manager/cluster-issuer.yaml"
kubectl apply -f "$REPO_ROOT/deployment/kubernetes/secrets/secret-store.yaml"
kubectl apply -f "$REPO_ROOT/deployment/kubernetes/secrets/vault-token-secret.yaml"
kubectl apply -f "$REPO_ROOT/deployment/kubernetes/secrets/externalsecret.yaml"
kubectl apply -k "$REPO_ROOT/deployment/kubernetes/overlays/dev"

echo "Bootstrap complete. Verify Argo CD and the app workloads with:"
echo "kubectl -n argocd get pods"
echo "kubectl -n agentic-platform get pods"
