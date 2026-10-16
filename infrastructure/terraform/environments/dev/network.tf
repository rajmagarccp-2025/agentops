module "dev_network" {
  source = "../../modules/networking"

  vpc_name    = "agentic-platform-dev"
  cidr_block  = "10.10.0.0/16"
  subnet_cidrs = ["10.10.1.0/24", "10.10.2.0/24"]
}

module "dev_database" {
  source = "../../modules/database"

  database_name     = "agentic_platform_dev"
  database_user     = "platform"
  database_password = "replace-with-secure-password"
}
