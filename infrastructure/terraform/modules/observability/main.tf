variable "service_name" {
  type = string
}

variable "otel_endpoint" {
  type    = string
  default = "http://otel-collector:4317"
}

resource "null_resource" "observability_placeholder" {
  triggers = {
    service_name = var.service_name
    otel_endpoint = var.otel_endpoint
  }
}

output "namespace" {
  value = "observability"
}
