# AWS Cloud Integration Guide

## Preferred Architecture Pattern

```text
MCP Gateway -> STS AssumeRole -> Tenant IAM Role -> AWS API
```

## AWS Services Utilized

- **EKS**: Managed Kubernetes cluster.
- **RDS PostgreSQL**: Transactional state and pgvector RAG store.
- **ElastiCache Redis**: Distributed cache and locks.
- **S3**: Audit log archive and evidence storage.
- **ALB**: Application loadbalancer with TLS termination.
- **Secrets Manager**: Production secret references.
