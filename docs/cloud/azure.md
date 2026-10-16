# Azure Cloud Integration Guide

## Preferred Architecture Pattern

```text
MCP Gateway -> Managed Identity / Workload Identity -> Microsoft Entra -> Azure RBAC -> Azure API
```

## Azure Services Utilized

- **AKS**: Azure Kubernetes Service.
- **Azure Database for PostgreSQL**: Database with pgvector extension.
- **Azure Cache for Redis**: Distributed caching.
- **Blob Storage**: Immutable audit log storage.
- **Key Vault**: Managed secrets store.
