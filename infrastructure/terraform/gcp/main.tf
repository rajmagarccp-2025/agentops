provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "current" {
  project_id = var.project_id
}

variable "project_id" {
  description = "Approved Google Cloud project ID for this deployment."
  type        = string

  validation {
    condition     = length(trimspace(var.project_id)) > 0
    error_message = "project_id must be set to an approved Google Cloud project."
  }
}

variable "project_name" {
  description = "Resource-name prefix approved for this deployment."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,29}$", var.project_name))
    error_message = "project_name must start with a lowercase letter and contain only lowercase letters, digits, or hyphens (maximum 30 characters)."
  }
}

variable "environment" {
  description = "Deployment environment, such as dev, staging, or prod."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "namespace" {
  description = "Kubernetes namespace bound to the workload identity."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", var.namespace)) && length(var.namespace) <= 63
    error_message = "namespace must be a valid Kubernetes DNS label of at most 63 characters."
  }
}

variable "service_account_name" {
  description = "GCP runtime service account bound to the Kubernetes workload identity."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.service_account_name))
    error_message = "service_account_name must be a valid GCP service account ID of 6 to 30 lowercase letters, digits, or hyphens."
  }
}

variable "region" {
  description = "Approved Google Cloud region for this deployment."
  type        = string

  validation {
    condition     = length(trimspace(var.region)) > 0
    error_message = "region must be set to an approved Google Cloud region."
  }
}

variable "cluster_release_channel" {
  type    = string
  default = "REGULAR"
}

variable "database_password" {
  type      = string
  sensitive = true
}

variable "enable_public_edge" {
  description = "Reserve public edge resources (global IP and Cloud Armor). Does not create DNS records."
  type        = bool
  default     = false
}

variable "enable_public_dns_record" {
  description = "Create an A record in the explicitly named existing DNS zone. Requires review before apply."
  type        = bool
  default     = false
}

variable "public_domain" {
  description = "Owned public hostname for the gateway, without a trailing dot."
  type        = string
  default     = ""

  validation {
    condition = var.public_domain == "" || can(
      regex("^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z]{2,63}$", var.public_domain)
    )
    error_message = "public_domain must be a fully qualified lowercase DNS hostname."
  }
}

variable "dns_managed_zone" {
  description = "Name of an existing Cloud DNS managed zone owned by this project."
  type        = string
  default     = ""
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

resource "google_project_service" "public_edge" {
  count   = var.enable_public_edge ? 1 : 0
  project = var.project_id
  service = "networkservices.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "public_dns" {
  count   = var.enable_public_dns_record ? 1 : 0
  project = var.project_id
  service = "dns.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "certificate_manager" {
  count   = var.enable_public_dns_record ? 1 : 0
  project = var.project_id
  service = "certificatemanager.googleapis.com"

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

resource "google_compute_global_address" "public_edge" {
  count        = var.enable_public_edge ? 1 : 0
  name         = "${var.project_name}-${var.environment}-public-edge"
  address_type = "EXTERNAL"
  ip_version   = "IPV4"

  depends_on = [google_project_service.public_edge]
}

resource "google_compute_security_policy" "public_edge" {
  count       = var.enable_public_edge ? 1 : 0
  name        = "${var.project_name}-${var.environment}-edge"
  description = "Cloud Armor baseline for the AgentOps Kong Gateway."

  rule {
    action      = "throttle"
    priority    = 1000
    description = "Apply a conservative per-client-IP request rate limit."

    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }

    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"

      rate_limit_threshold {
        count        = 300
        interval_sec = 60
      }
    }
  }

  rule {
    action      = "deny(403)"
    priority    = 1100
    description = "Preview SQL injection WAF signatures before enforcement."
    preview     = true

    match {
      expr {
        expression = "evaluatePreconfiguredWaf('sqli-v33-stable')"
      }
    }
  }

  rule {
    action      = "deny(403)"
    priority    = 1200
    description = "Preview cross-site scripting WAF signatures before enforcement."
    preview     = true

    match {
      expr {
        expression = "evaluatePreconfiguredWaf('xss-v33-stable')"
      }
    }
  }

  rule {
    action   = "allow"
    priority = 2147483647
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }

  depends_on = [google_project_service.public_edge]
}

data "google_dns_managed_zone" "public_edge" {
  count = var.enable_public_dns_record ? 1 : 0
  name  = var.dns_managed_zone

  lifecycle {
    precondition {
      condition = (
        var.enable_public_edge && var.public_domain != "" && var.dns_managed_zone != ""
      )
      error_message = "Public DNS requires the public edge, a public domain, and an existing managed zone name."
    }
  }

  depends_on = [google_project_service.public_dns]
}

resource "google_dns_record_set" "public_edge" {
  count        = var.enable_public_dns_record ? 1 : 0
  name         = "${var.public_domain}."
  managed_zone = data.google_dns_managed_zone.public_edge[0].name
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_global_address.public_edge[0].address]

  depends_on = [google_project_service.public_dns]
}

resource "google_certificate_manager_dns_authorization" "public_edge" {
  count       = var.enable_public_dns_record ? 1 : 0
  name        = "${var.project_name}-${var.environment}-authorization"
  description = "DNS authorization for the AgentOps public gateway certificate."
  domain      = var.public_domain

  depends_on = [google_project_service.certificate_manager]
}

resource "google_dns_record_set" "certificate_authorization" {
  count        = var.enable_public_dns_record ? 1 : 0
  name         = google_certificate_manager_dns_authorization.public_edge[0].dns_resource_record[0].name
  managed_zone = data.google_dns_managed_zone.public_edge[0].name
  type         = google_certificate_manager_dns_authorization.public_edge[0].dns_resource_record[0].type
  ttl          = 300
  rrdatas      = [google_certificate_manager_dns_authorization.public_edge[0].dns_resource_record[0].data]

  depends_on = [google_project_service.public_dns]
}

resource "google_certificate_manager_certificate" "public_edge" {
  count       = var.enable_public_dns_record ? 1 : 0
  name        = "${var.project_name}-${var.environment}-certificate"
  description = "Google-managed TLS certificate for the AgentOps public gateway."

  managed {
    domains            = [var.public_domain]
    dns_authorizations = [google_certificate_manager_dns_authorization.public_edge[0].id]
  }
}

resource "google_certificate_manager_certificate_map" "public_edge" {
  count       = var.enable_public_dns_record ? 1 : 0
  name        = "${var.project_name}-${var.environment}-certificate-map"
  description = "Certificate map for the AgentOps public gateway."

  depends_on = [google_project_service.certificate_manager]
}

resource "google_certificate_manager_certificate_map_entry" "public_edge" {
  count        = var.enable_public_dns_record ? 1 : 0
  name         = "${var.project_name}-${var.environment}-certificate"
  description  = "Hostname entry for the AgentOps public gateway certificate."
  map          = google_certificate_manager_certificate_map.public_edge[0].id
  hostname     = var.public_domain
  certificates = [google_certificate_manager_certificate.public_edge[0].id]
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

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }

  depends_on = [google_project_service.required]
}

resource "google_pubsub_subscription" "dead_letter" {
  name  = "${var.project_name}-${var.environment}-events-dlq"
  topic = google_pubsub_topic.dead_letter.id

  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"

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
  pubsub_service_agent_email = "service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
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

resource "google_pubsub_subscription_iam_member" "pubsub_service_agent_events_subscriber" {
  subscription = google_pubsub_subscription.events.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${local.pubsub_service_agent_email}"
}

resource "google_pubsub_topic_iam_member" "pubsub_service_agent_dead_letter_publisher" {
  topic  = google_pubsub_topic.dead_letter.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${local.pubsub_service_agent_email}"
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
    activation_policy = "ALWAYS"
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

output "public_edge_ip" {
  description = "Reserved global address for the opt-in Gateway API edge."
  value       = try(google_compute_global_address.public_edge[0].address, null)
}

output "public_edge_ip_name" {
  description = "Global address resource name to reference from the GKE Gateway."
  value       = try(google_compute_global_address.public_edge[0].name, null)
}

output "public_edge_cloud_armor_policy_name" {
  description = "Cloud Armor policy name to reference from the Kong GCPBackendPolicy."
  value       = try(google_compute_security_policy.public_edge[0].name, null)
}

output "public_edge_certificate_map" {
  description = "Certificate Manager map resource ID for the opt-in GKE Gateway."
  value       = try(google_certificate_manager_certificate_map.public_edge[0].id, null)
}

output "artifact_bucket_name" {
  value = google_storage_bucket.artifacts.name
}

output "pubsub_topic_name" {
  value = google_pubsub_topic.events.name
}

output "pubsub_subscription_name" {
  value = google_pubsub_subscription.events.name
}

output "pubsub_dead_letter_subscription_name" {
  value = google_pubsub_subscription.dead_letter.name
}

output "kms_key_name" {
  value = google_kms_crypto_key.platform.id
}

output "artifact_registry_repository" {
  value = google_artifact_registry_repository.platform.name
}
