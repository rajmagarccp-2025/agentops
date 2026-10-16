module "staging_network" {
  source = "../../modules/networking"

  vpc_name    = "agentic-platform-staging"
  cidr_block  = "10.20.0.0/16"
  subnet_cidrs = ["10.20.1.0/24", "10.20.2.0/24"]
}

module "staging_database" {
  source = "../../modules/database"

  database_name     = "agentic_platform_staging"
  database_user     = "platform"
  database_password = "replace-with-secure-password"
}
