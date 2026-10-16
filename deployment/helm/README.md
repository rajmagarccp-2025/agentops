# Helm Charts

The Phase 18 `agentic-platform` chart deploys the API and web workloads with
configurable images, resources, probes, services, ConfigMap/Secret references,
HPA, and PDB settings.

Render locally:

```text
helm template agentic-platform ./agentic-platform --namespace agentic-platform
```

Install with deployment-time secret values:

```text
helm upgrade --install agentic-platform ./agentic-platform \
	--namespace agentic-platform --create-namespace \
	--set-string secrets.jwtDemoSecret=$JWT_DEMO_SECRET \
	--set-string secrets.databaseUrl=$DATABASE_URL
```
