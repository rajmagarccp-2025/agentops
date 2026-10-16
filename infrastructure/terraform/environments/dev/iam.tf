module "dev_iam" {
  source = "../../modules/iam"

  project_name = "agentic-platform-dev"
  role_name    = "platform-operator-dev"
}

module "dev_observability" {
  source = "../../modules/observability"

  service_name = "agentic-platform-api"
  otel_endpoint = "http://otel-collector:4317"
}
