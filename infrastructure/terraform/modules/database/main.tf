variable "database_name" {
  type = string
}

variable "database_user" {
  type = string
}

variable "database_password" {
  type      = string
  sensitive = true
}

resource "null_resource" "database_placeholder" {
  triggers = {
    database_name = var.database_name
    database_user = var.database_user
    password_hash = sha256(var.database_password)
  }
}

output "connection_string" {
  value     = "postgresql://user:password@host:5432/${var.database_name}"
  sensitive = true
}
