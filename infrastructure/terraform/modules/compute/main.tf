variable "cluster_name" {
  type = string
}

variable "node_count" {
  type    = number
  default = 2
}

variable "instance_size" {
  type    = string
  default = "standard-2"
}

resource "null_resource" "compute_placeholder" {
  triggers = {
    cluster_name = var.cluster_name
    node_count   = tostring(var.node_count)
    instance_size = var.instance_size
  }
}

output "compute_id" {
  value = "${var.cluster_name}-compute"
}
