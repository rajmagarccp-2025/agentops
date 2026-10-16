# Database Runbook

## Health

The API readiness endpoint runs `SELECT 1` against PostgreSQL. Check it before
investigating application errors:

```text
curl https://app.example.com/api/v1/health/ready
kubectl -n agentic-platform logs deployment/platform-api --since=15m
```

## Migrations

Run migrations before starting a new application version:

```text
make migrate
```

Generate SQL for review without connecting to PostgreSQL:

```text
Push-Location backend
..\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head --sql
Pop-Location
```

Never edit an applied migration. Add a new forward and reversible revision.

## Recovery

1. Stop promotion and mark the release unhealthy.
2. Confirm connection saturation, lock waits, storage, and provider health.
3. Scale API workers only after checking database pool limits.
4. Restore from the provider snapshot or point-in-time recovery process.
5. Validate migrations and run `/api/v1/health/ready` before reopening traffic.

Database passwords must come from the external secret manager. Never place them
in Terraform, Kubernetes manifests, logs, or support tickets.
