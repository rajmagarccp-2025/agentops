terraform {
  required_version = ">= 1.7.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.31"
    }
  }
}

provider "kubernetes" {
  config_path = "~/.kube/config"
}

module "dev_cluster" {
  source = "../../modules/kubernetes-cluster"

  cluster_name = "agentic-platform-dev"
  namespace    = "agentic-platform-dev"
  environment  = "dev"
}
