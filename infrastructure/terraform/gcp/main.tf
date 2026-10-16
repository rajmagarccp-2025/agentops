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

variable "namespace" {
  type    = string
  default = "platform-prod"
}

variable "service_account_name" {
  type    = string
  default = "platform-sa-gcp"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "cluster_release_channel" {
  type    = string
  default = "REGULAR"
}

variable "database_password" {
  type      = string
  sensitive = true
}

resource "google_project_service" "required" {
  for_each = toset([
    "compute.googleapis.com",
    "container.googleapis.com",
    "artifactregistry.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "iam.googleapis.com",
    "servicenetworking.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "platform" {
  name                    = "${var.project_name}-${var.environment}-vpc"
  auto_create_subnetworks = false

  depends_on = [google_project_service.required]
}

resource "google_compute_subnetwork" "platform" {
  name          = "${var.project_name}-${var.environment}-subnet"
  ip_cidr_range = "10.50.0.0/16"
  region        = var.region
  network       = google_compute_network.platform.id

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.51.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.52.0.0/20"
  }

  depends_on = [google_project_service.required]
}

resource "google_compute_global_address" "private_ip_alloc" {
  name          = "${var.project_name}-${var.environment}-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.platform.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.platform.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_alloc.name]

  depends_on = [google_project_service.required]
}

resource "google_container_cluster" "platform" {
  name       = "${var.project_name}-${var.environment}"
  location   = var.region
  network    = google_compute_network.platform.name
  subnetwork = google_compute_subnetwork.platform.name

  enable_autopilot    = true
  deletion_protection = var.environment == "prod"

  release_channel {
    channel = var.cluster_release_channel
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  depends_on = [google_project_service.required]
}

# Artifact Registry Repository
resource "google_artifact_registry_repository" "platform" {
  location      = var.region
  repository_id = "${var.project_name}-${var.environment}"
  description   = "Docker container registry for Platform images"
  format        = "DOCKER"

  depends_on = [google_project_service.required]
}

# GCP Service Account for Workload Identity
resource "google_service_account" "platform" {
  account_id   = var.service_account_name
  display_name = "Platform Workload Identity SA"
}

resource "google_service_account_iam_member" "workload_identity_user" {
  service_account_id = google_service_account.platform.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.namespace}/${var.service_account_name}]"
}

# Memorystore Redis Instance
resource "google_redis_instance" "platform" {
  name               = "${var.project_name}-${var.environment}-redis"
  tier               = var.environment == "prod" ? "STANDARD_HA" : "BASIC"
  memory_size_gb     = var.environment == "prod" ? 4 : 1
  region             = var.region
  location_id        = "${var.region}-a"
  authorized_network = google_compute_network.platform.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  depends_on = [
    google_project_service.required,
    google_service_networking_connection.private_vpc_connection,
  ]
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

    database_flags {
      name  = "cloudsql.enable_pgvector"
      value = "on"
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.platform.id
    }
  }

  deletion_protection = var.environment == "prod"

  depends_on = [
    google_project_service.required,
    google_service_networking_connection.private_vpc_connection,
  ]
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

