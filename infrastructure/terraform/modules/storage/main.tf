variable "storage_name" {
  type = string
}

variable "size_gb" {
  type    = number
  default = 50
}

resource "null_resource" "storage_placeholder" {
  triggers = {
    storage_name = var.storage_name
    size_gb     = tostring(var.size_gb)
  }
}

output "storage_id" {
  value = "${var.storage_name}-storage"
}
