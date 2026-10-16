variable "project_name" {
  type = string
}

variable "role_name" {
  type    = string
  default = "platform-operator"
}

resource "null_resource" "iam_placeholder" {
  triggers = {
    project_name = var.project_name
    role_name    = var.role_name
  }
}

output "role_name" {
  value = var.role_name
}
