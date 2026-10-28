terraform {
  required_version = ">= 1.7.0"

  backend "gcs" {
    # Customer-specific bucket and prefix are supplied by the infrastructure workflow.
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}
