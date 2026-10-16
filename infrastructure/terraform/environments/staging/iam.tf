module "staging_iam" {
  source = "../../modules/iam"

  project_name = "agentic-platform-staging"
  role_name    = "platform-operator-staging"
}

module "staging_observability" {
  source = "../../modules/observability"

  service_name = "agentic-platform-api"
  otel_endpoint = "http://otel-collector:4317"
}
