module "prod_network" {
  source = "../../modules/networking"

  vpc_name    = "agentic-platform-prod"
  cidr_block  = "10.30.0.0/16"
  subnet_cidrs = ["10.30.1.0/24", "10.30.2.0/24"]
}

module "prod_database" {
  source = "../../modules/database"

  database_name     = "agentic_platform_prod"
  database_user     = "platform"
  database_password = "replace-with-secure-password"
}
