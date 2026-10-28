# =============================================================================
# HealDeploy — Terraform Outputs
# =============================================================================

output "resource_group_name" {
  description = "Name of the provisioned Azure Resource Group"
  value       = azurerm_resource_group.rg.name
}

output "vm_name" {
  description = "Name of the provisioned Linux Virtual Machine"
  value       = azurerm_linux_virtual_machine.vm.name
}

output "public_ip_address" {
  description = "Static Public IP address assigned to the virtual machine"
  value       = azurerm_public_ip.pip.ip_address
}

output "ssh_connection_command" {
  description = "Command for SSH access using the configured administrator key"
  value       = "ssh -i ~/.ssh/healdeploy_rsa ${var.admin_username}@${azurerm_public_ip.pip.ip_address}"
}

output "application_http_url" {
  description = "HTTP URL for web access (proxied through Nginx on port 80)"
  value       = "http://${azurerm_public_ip.pip.ip_address}/"
}

output "health_endpoint_url" {
  description = "Health check endpoint URL used by Jenkins deployment verification"
  value       = "http://${azurerm_public_ip.pip.ip_address}/health"
}
