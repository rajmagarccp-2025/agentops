variable "project_name" {
  type = string
}

variable "enforce_tls" {
  type    = bool
  default = true
}

variable "logging_enabled" {
  type    = bool
  default = true
}

resource "null_resource" "security_placeholder" {
  triggers = {
    project_name     = var.project_name
    enforce_tls     = tostring(var.enforce_tls)
    logging_enabled = tostring(var.logging_enabled)
  }
}

output "policy" {
  value = "tls-enforced=${var.enforce_tls},logging-enabled=${var.logging_enabled}"
}
