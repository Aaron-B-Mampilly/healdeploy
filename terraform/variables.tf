# =============================================================================
# HealDeploy — Terraform Variables
# =============================================================================

variable "subscription_id" {
  description = "Azure Subscription ID for the target deployment"
  type        = string
}

variable "location" {
  description = "Azure region where resources will be provisioned"
  type        = string
  default     = "eastasia"
}

variable "resource_group_name" {
  description = "Name of the Azure Resource Group"
  type        = string
  default     = "rg-healdeploy-eastasia"
}

variable "vnet_name" {
  description = "Name of the Virtual Network"
  type        = string
  default     = "vnet-healdeploy"
}

variable "vnet_address_space" {
  description = "Address range for the Virtual Network in CIDR notation"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "subnet_name" {
  description = "Name of the application subnet"
  type        = string
  default     = "snet-healdeploy-app"
}

variable "subnet_address_prefix" {
  description = "Address prefix for the application subnet in CIDR notation"
  type        = list(string)
  default     = ["10.0.1.0/24"]
}

variable "nsg_name" {
  description = "Name of the Network Security Group"
  type        = string
  default     = "nsg-healdeploy"
}

variable "public_ip_name" {
  description = "Name of the public IP resource"
  type        = string
  default     = "pip-healdeploy-vm"
}

variable "nic_name" {
  description = "Name of the Network Interface"
  type        = string
  default     = "nic-healdeploy-vm"
}

variable "vm_name" {
  description = "Name of the Linux Virtual Machine"
  type        = string
  default     = "vm-healdeploy-prod"
}

variable "vm_size" {
  description = "Azure VM SKU size"
  type        = string
  default     = "Standard_D2s_v4"
}

variable "admin_username" {
  description = "Administrator username for the Linux VM"
  type        = string
  default     = "azureuser"
}

variable "ssh_public_key" {
  description = "SSH public key content for authenticating to the Linux VM"
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "Public IP address or CIDR permitted to connect via SSH (port 22)"
  type        = string
  default     = "14.139.187.145/32"
}

variable "tags" {
  description = "Resource tags applied to all provisioned infrastructure"
  type        = map(string)
  default = {
    Project     = "HealDeploy"
    Environment = "production"
    ManagedBy   = "Terraform"
  }
}
