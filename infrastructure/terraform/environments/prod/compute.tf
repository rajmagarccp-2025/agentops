module "prod_compute" {
  source = "../../modules/compute"

  cluster_name = "agentic-platform-prod"
  node_count   = 4
  instance_size = "standard-4"
}

module "prod_storage" {
  source = "../../modules/storage"

  storage_name = "agentic-platform-prod"
  size_gb      = 200
}
