module "staging_compute" {
  source = "../../modules/compute"

  cluster_name = "agentic-platform-staging"
  node_count   = 3
  instance_size = "standard-4"
}

module "staging_storage" {
  source = "../../modules/storage"

  storage_name = "agentic-platform-staging"
  size_gb      = 100
}
