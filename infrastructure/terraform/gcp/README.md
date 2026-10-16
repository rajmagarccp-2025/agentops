# GCP deployment scaffolding

This module provisions the initial GKE Autopilot base for the platform on Google Cloud.

## Required inputs

- `project_id`: the Google Cloud project hosting the platform
- `database_password`: secure Postgres password for the Cloud SQL instance

## Example usage

```bash
cd infrastructure/terraform/gcp
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan -var-file="terraform.tfvars"
terraform apply -var-file="terraform.tfvars"
```

## Provisioned resources

- GKE Autopilot cluster
- VPC and subnet with secondary ranges for Pods and Services
- Private Service Networking for Cloud SQL and Redis access
- Artifact Registry repository
- Cloud SQL for PostgreSQL with pgvector enabled
- Memorystore Redis instance
- Workload Identity service account binding
- Required GCP APIs

## Notes

- The deployment keeps provider-specific resources isolated under `infrastructure/terraform/gcp`.
- Workload Identity binds the Kubernetes service account to the GCP service account using the `namespace` and `service_account_name` variables.
- Private networking is enabled for Cloud SQL and Redis so the app runs inside the VPC rather than exposing public database endpoints.
- For production, set `environment = "prod"` and protect Terraform state with a remote backend.
