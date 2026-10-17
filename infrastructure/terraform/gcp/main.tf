provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "current" {
  project_id = var.project_id
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
    "aiplatform.googleapis.com",
    "pubsub.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudkms.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudtrace.googleapis.com",
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

resource "google_project_iam_member" "gke_artifact_registry_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"
}

resource "google_storage_bucket" "artifacts" {
  name                        = "${var.project_id}-agentops-artifacts"
  location                    = "US"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  labels = {
    application = "agentops"
    environment = var.environment
    purpose     = "application-artifacts"
  }

  depends_on = [google_project_service.required]
}

resource "google_pubsub_topic" "events" {
  name = "${var.project_name}-${var.environment}-events"

  depends_on = [google_project_service.required]
}

resource "google_pubsub_topic" "dead_letter" {
  name = "${var.project_name}-${var.environment}-events-dlq"

  depends_on = [google_project_service.required]
}

resource "google_pubsub_subscription" "events" {
  name  = "${var.project_name}-${var.environment}-events"
  topic = google_pubsub_topic.events.id

  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }

  depends_on = [google_project_service.required]
}

resource "google_kms_key_ring" "platform" {
  name     = "${var.project_name}-${var.environment}"
  location = var.region

  depends_on = [google_project_service.required]
}

resource "google_kms_crypto_key" "platform" {
  name            = "${var.project_name}-${var.environment}-application"
  key_ring        = google_kms_key_ring.platform.id
  rotation_period = "7776000s"

  lifecycle {
    prevent_destroy = true
  }
}

locals {
  platform_secret_ids = toset([
    "agentops-database-url",
    "agentops-redis-url",
    "agentops-jwt-secret",
    "agentops-oidc-issuer",
    "agentops-oidc-client-id",
    "agentops-oidc-client-secret",
  ])
}

resource "google_secret_manager_secret" "platform" {
  for_each  = local.platform_secret_ids
  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

# GCP Service Account for Workload Identity
resource "google_service_account" "platform" {
  account_id   = var.service_account_name
  display_name = "Platform Workload Identity SA"

  depends_on = [google_project_service.required]
}

resource "google_service_account_iam_member" "workload_identity_user" {
  service_account_id = google_service_account.platform.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.namespace}/${var.service_account_name}]"

  depends_on = [google_container_cluster.platform]
}

resource "google_storage_bucket_iam_member" "platform_object_user" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.platform.email}"
}

resource "google_pubsub_topic_iam_member" "platform_events_publisher" {
  topic  = google_pubsub_topic.events.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.platform.email}"
}

resource "google_pubsub_subscription_iam_member" "platform_events_subscriber" {
  subscription = google_pubsub_subscription.events.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.platform.email}"
}

resource "google_secret_manager_secret_iam_member" "platform_secret_accessor" {
  for_each  = local.platform_secret_ids
  secret_id = google_secret_manager_secret.platform[each.value].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.platform.email}"
}

resource "google_kms_crypto_key_iam_member" "platform_crypto_key_user" {
  crypto_key_id = google_kms_crypto_key.platform.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_service_account.platform.email}"
}

resource "google_project_iam_member" "platform_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.platform.email}"
}

resource "google_project_iam_member" "platform_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.platform.email}"
}

resource "google_project_iam_member" "platform_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.platform.email}"
}

resource "google_project_iam_member" "platform_trace_agent" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.platform.email}"
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

resource "google_sql_database" "platform" {
  name     = "agentops"
  instance = google_sql_database_instance.platform.name
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

output "database_private_ip" {
  value = google_sql_database_instance.platform.private_ip_address
}

output "artifact_bucket_name" {
  value = google_storage_bucket.artifacts.name
}

output "pubsub_topic_name" {
  value = google_pubsub_topic.events.name
}

output "kms_key_name" {
  value = google_kms_crypto_key.platform.id
}

output "artifact_registry_repository" {
  value = google_artifact_registry_repository.platform.name
}
