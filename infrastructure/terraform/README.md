# Terraform

Cloud infrastructure modules and environments.

## Current foundation

- `aws/`: concrete AWS VPC, public/private subnets, EKS cluster, RDS Postgres,
  KMS, CloudTrail, VPC flow logs, WAF, and security baseline
- `providers/`: AWS, Azure, and GCP provider entrypoints
- `modules/`: reusable Kubernetes, database, networking, compute, storage, IAM,
  observability, and security boundaries
- `environments/`: dev, staging, and prod composition examples

The AWS baseline expects `database_password` to be supplied through a secure
Terraform variable or secret manager. It intentionally does not include real
credentials.

Terraform CLI validation should be run from the selected environment after
credentials and backend configuration are supplied:

```text
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan -var-file=terraform.tfvars
```
