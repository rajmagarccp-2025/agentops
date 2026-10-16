module "prod_iam" {
  source = "../../modules/iam"

  project_name = "agentic-platform-prod"
  role_name    = "platform-operator-prod"
}

module "prod_observability" {
  source = "../../modules/observability"

  service_name = "agentic-platform-api"
  otel_endpoint = "http://otel-collector:4317"
}
