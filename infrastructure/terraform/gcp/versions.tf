terraform {
  required_version = ">= 1.7.0"

  backend "gcs" {
    bucket = "project-cks-aug2026-agentops-tofu-state"
    prefix = "agentops/prod"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}
