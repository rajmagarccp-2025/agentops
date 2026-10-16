# Terraform remote state

Each cloud has a backend configuration example:

- `aws.tfbackend.example`: S3 state with DynamoDB locking and encryption
- `azure.tfbackend.example`: Azure Storage state with Entra ID authentication
- `gcp.tfbackend.example`: GCS state with environment prefixing

## Usage

Copy the relevant example to a local, ignored file and replace every placeholder
through environment-specific deployment automation:

```text
terraform init -backend-config=aws.tfbackend
terraform plan -var-file=terraform.tfvars
```

Never commit backend credentials, state files, storage account keys, or real
resource names. Remote state must use versioning, encryption, access logging, and
least-privilege CI identities. State migration requires an explicit change plan
and backup before running `terraform init -migrate-state`.
