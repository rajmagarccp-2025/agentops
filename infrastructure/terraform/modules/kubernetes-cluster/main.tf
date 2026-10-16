variable "cluster_name" {
  type = string
}

variable "namespace" {
  type = string
}

variable "environment" {
  type = string
}

resource "kubernetes_namespace" "platform" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/part-of" = "agentic-platform"
      environment                 = var.environment
    }
  }
}

resource "kubernetes_config_map_v1" "platform_config" {
  metadata {
    name      = "platform-config"
    namespace = kubernetes_namespace.platform.metadata[0].name
  }

  data = {
    APP_ENV          = var.environment
    LOG_LEVEL        = "INFO"
    DEMO_MODE        = "false"
    OTEL_SERVICE_NAME = "agentic-platform-api"
  }
}
