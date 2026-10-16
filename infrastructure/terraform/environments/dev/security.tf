module "dev_security" {
  source = "../../modules/security"

  project_name    = "agentic-platform-dev"
  enforce_tls     = true
  logging_enabled = true
}
