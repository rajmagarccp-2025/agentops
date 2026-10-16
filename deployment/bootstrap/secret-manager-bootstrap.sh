#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_NAMESPACE="agentic-platform"
EXTERNAL_SECRETS_NAMESPACE="external-secrets"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required but not installed." >&2
  exit 1
fi

if [[ -z "${VAULT_ADDR:-}" || -z "${VAULT_TOKEN:-}" ]]; then
  echo "VAULT_ADDR and VAULT_TOKEN must be set before bootstrapping the secret manager." >&2
  exit 1
fi

JWT_DEMO_SECRET="${JWT_DEMO_SECRET:-$(openssl rand -base64 32 2>/dev/null || python - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)}"
POSTGRES_DB="${POSTGRES_DB:-platform}"
POSTGRES_USER="${POSTGRES_USER:-platform}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(openssl rand -base64 32 2>/dev/null || python - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)}"
DATABASE_URL="${DATABASE_URL:-postgresql://platform:${POSTGRES_PASSWORD}@postgresql:5432/${POSTGRES_DB}}"

kubectl create namespace "$EXTERNAL_SECRETS_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace "$TARGET_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic vault-token \
  --namespace "$EXTERNAL_SECRETS_NAMESPACE" \
  --from-literal=token="$VAULT_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "$TARGET_NAMESPACE" create secret generic platform-secrets \
  --from-literal=JWT_DEMO_SECRET="$JWT_DEMO_SECRET" \
  --from-literal=POSTGRES_DB="$POSTGRES_DB" \
  --from-literal=POSTGRES_USER="$POSTGRES_USER" \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=DATABASE_URL="$DATABASE_URL" \
  --dry-run=client -o yaml | kubectl apply -f -

cat <<EOF | kubectl apply -f -
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: cluster-secret-store
spec:
  provider:
    vault:
      server: ${VAULT_ADDR}
      path: secret
      version: v2
      auth:
        tokenSecretRef:
          name: vault-token
          key: token
          namespace: ${EXTERNAL_SECRETS_NAMESPACE}
EOF

cat <<EOF | kubectl apply -f -
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: platform-secrets
  namespace: ${TARGET_NAMESPACE}
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: cluster-secret-store
    kind: ClusterSecretStore
  target:
    name: platform-secrets
    creationPolicy: Owner
  data:
    - secretKey: JWT_DEMO_SECRET
      remoteRef:
        key: agentic-platform/jwt-demo-secret
    - secretKey: POSTGRES_DB
      remoteRef:
        key: agentic-platform/postgres-db
    - secretKey: POSTGRES_USER
      remoteRef:
        key: agentic-platform/postgres-user
    - secretKey: POSTGRES_PASSWORD
      remoteRef:
        key: agentic-platform/postgres-password
    - secretKey: DATABASE_URL
      remoteRef:
        key: agentic-platform/database-url
EOF

echo "External Secrets bootstrap complete."
echo "Set VAULT_ADDR, VAULT_TOKEN, and optionally JWT_DEMO_SECRET/POSTGRES_PASSWORD/DATABASE_URL before running this script in a real cluster."
