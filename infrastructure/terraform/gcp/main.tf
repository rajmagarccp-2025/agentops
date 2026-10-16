provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  type = string
}

variable "project_name" {
  type    = string
  default = "agentic-platform"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "database_password" {
  type      = string
  sensitive = true
}

resource "google_compute_network" "platform" {
  name                    = "${var.project_name}-${var.environment}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "platform" {
  name          = "${var.project_name}-${var.environment}-subnet"
  ip_cidr_range = "10.50.0.0/16"
  region        = var.region
  network       = google_compute_network.platform.id
}

resource "google_container_cluster" "platform" {
  name                     = "${var.project_name}-${var.environment}"
  location                 = var.region
  network                  = google_compute_network.platform.name
  subnetwork               = google_compute_subnetwork.platform.name
  remove_default_node_pool = true
  initial_node_count       = 1
  deletion_protection      = var.environment == "prod"

  ip_allocation_policy {}

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
}

resource "google_container_node_pool" "platform" {
  name       = "${var.project_name}-${var.environment}-nodes"
  location   = var.region
  cluster    = google_container_cluster.platform.name
  node_count = var.environment == "prod" ? 3 : 1

  node_config {
    machine_type = var.environment == "prod" ? "e2-standard-4" : "e2-standard-2"
    workload_metadata_config {
      mode = "GKE_METADATA"
    }
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]
  }
}

# Artifact Registry Repository
resource "google_artifact_registry_repository" "platform" {
  location      = var.region
  repository_id = "${var.project_name}-${var.environment}"
  description   = "Docker container registry for Platform images"
  format        = "DOCKER"
}

# GCP Service Account for Workload Identity
resource "google_service_account" "platform" {
  account_id   = "${var.project_name}-${var.environment}-sa"
  display_name = "Platform Workload Identity SA"
}

resource "google_service_account_iam_member" "workload_identity_user" {
  service_account_id = google_service_account.platform.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[platform-prod/platform-sa]"
}

# Memorystore Redis Instance
resource "google_redis_instance" "platform" {
  name           = "${var.project_name}-${var.environment}-redis"
  tier           = var.environment == "prod" ? "STANDARD_HA" : "BASIC"
  memory_size_gb = var.environment == "prod" ? 4 : 1
  region         = var.region
  location_id    = "${var.region}-a"
  authorized_network = google_compute_network.platform.id
}

resource "google_sql_database_instance" "platform" {
  name             = "${var.project_name}-${var.environment}-db"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier              = var.environment == "prod" ? "db-custom-4-15360" : "db-f1-micro"
    availability_type = var.environment == "prod" ? "REGIONAL" : "ZONAL"
    disk_size         = var.environment == "prod" ? 200 : 50
    disk_type         = "PD_SSD"
    disk_autoresize   = true
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }
    ip_configuration {
      ipv4_enabled = false
    }
  }

  deletion_protection = var.environment == "prod"
}

resource "google_sql_user" "platform" {
  name     = "platform"
  instance = google_sql_database_instance.platform.name
  password = var.database_password
}

output "cluster_name" {
  value = google_container_cluster.platform.name
}

output "database_connection_name" {
  value = google_sql_database_instance.platform.connection_name
}

output "redis_host" {
  value = google_redis_instance.platform.host
}

output "artifact_registry_repository" {
  value = google_artifact_registry_repository.platform.name
}

