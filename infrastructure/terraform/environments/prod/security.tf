module "prod_security" {
  source = "../../modules/security"

  project_name    = "agentic-platform-prod"
  enforce_tls     = true
  logging_enabled = true
}
