module "staging_security" {
  source = "../../modules/security"

  project_name    = "agentic-platform-staging"
  enforce_tls     = true
  logging_enabled = true
}
