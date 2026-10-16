terraform {
  required_version = ">= 1.7.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = "agentic-platform-placeholder"
  region  = "us-central1"
}

resource "google_storage_bucket" "placeholder" {
  name     = "agentic-platform-placeholder"
  location = "US"
}
