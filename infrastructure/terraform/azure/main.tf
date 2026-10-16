provider "azurerm" {
  features {}
}

variable "project_name" {
  type    = string
  default = "agentic-platform"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "location" {
  type    = string
  default = "eastus"
}

variable "database_password" {
  type      = string
  sensitive = true
}

resource "azurerm_resource_group" "platform" {
  name     = "${var.project_name}-${var.environment}-rg"
  location = var.location
}

resource "azurerm_virtual_network" "platform" {
  name                = "${var.project_name}-${var.environment}-vnet"
  location            = azurerm_resource_group.platform.location
  resource_group_name = azurerm_resource_group.platform.name
  address_space       = ["10.40.0.0/16"]
}

resource "azurerm_subnet" "aks" {
  name                 = "aks-subnet"
  resource_group_name  = azurerm_resource_group.platform.name
  virtual_network_name = azurerm_virtual_network.platform.name
  address_prefixes     = ["10.40.1.0/24"]
}

resource "azurerm_kubernetes_cluster" "platform" {
  name                = "${var.project_name}-${var.environment}"
  location            = azurerm_resource_group.platform.location
  resource_group_name = azurerm_resource_group.platform.name
  dns_prefix          = "${var.project_name}-${var.environment}"

  default_node_pool {
    name       = "system"
    node_count = var.environment == "prod" ? 3 : 1
    vm_size    = var.environment == "prod" ? "Standard_D4s_v5" : "Standard_D2s_v5"
    vnet_subnet_id = azurerm_subnet.aks.id
  }

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_postgresql_flexible_server" "platform" {
  name                   = "${var.project_name}-${var.environment}-db"
  resource_group_name    = azurerm_resource_group.platform.name
  location               = azurerm_resource_group.platform.location
  version                = "16"
  administrator_login    = "platform"
  administrator_password = var.database_password
  storage_mb             = var.environment == "prod" ? 131072 : 32768
  sku_name               = var.environment == "prod" ? "GP_Standard_D4s_v3" : "B_Standard_B1ms"
}

output "resource_group_name" {
  value = azurerm_resource_group.platform.name
}

output "cluster_name" {
  value = azurerm_kubernetes_cluster.platform.name
}

output "database_fqdn" {
  value = azurerm_postgresql_flexible_server.platform.fqdn
}
