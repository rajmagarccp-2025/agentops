# GCP Cloud Integration Guide

## Preferred Architecture Pattern

```text
MCP Gateway -> Workload Identity -> GCP Service Account -> IAM -> GCP API
```

## GCP Services Utilized

- **GKE**: Google Kubernetes Engine.
- **Cloud SQL PostgreSQL**: Database with pgvector extension.
- **Memorystore Redis**: Distributed cache.
- **Cloud Storage**: Audit logs and evidence repository.
- **Secret Manager**: Production secret references.
