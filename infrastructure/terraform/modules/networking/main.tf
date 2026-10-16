variable "vpc_name" {
  type = string
}

variable "cidr_block" {
  type    = string
  default = "10.0.0.0/16"
}

variable "subnet_cidrs" {
  type    = list(string)
  default = ["10.0.1.0/24", "10.0.2.0/24"]
}

resource "null_resource" "network_placeholder" {
  triggers = {
    vpc_name     = var.vpc_name
    cidr_block   = var.cidr_block
    subnet_cidrs = join(",", var.subnet_cidrs)
  }
}

output "network_id" {
  value = "${var.vpc_name}-network"
}
