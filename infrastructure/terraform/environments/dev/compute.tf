module "dev_compute" {
  source = "../../modules/compute"

  cluster_name = "agentic-platform-dev"
  node_count   = 2
  instance_size = "standard-2"
}

module "dev_storage" {
  source = "../../modules/storage"

  storage_name = "agentic-platform-dev"
  size_gb      = 50
}
