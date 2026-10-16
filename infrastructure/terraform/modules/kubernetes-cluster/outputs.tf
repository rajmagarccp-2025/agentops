output "namespace" {
  value = kubernetes_namespace.platform.metadata[0].name
}

output "config_map_name" {
  value = kubernetes_config_map_v1.platform_config.metadata[0].name
}
