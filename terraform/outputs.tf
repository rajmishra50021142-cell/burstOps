# References, not values — state is a credential; keep secret material out of outputs.
output "function_app_name" {
  value = azurerm_function_app_flex_consumption.main.name
}

output "function_hostname" {
  value = "https://${azurerm_function_app_flex_consumption.main.default_hostname}/api/calculate"
}

output "app_insights_connection_string" {
  value     = azurerm_application_insights.main.connection_string
  sensitive = true
}

output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "location" {
  value = azurerm_resource_group.main.location
}

output "storage_account_name" {
  value = azurerm_storage_account.main.name
}

output "aks_cluster_name" {
  value = azurerm_kubernetes_cluster.main.name
}

output "acr_name" {
  value = azurerm_container_registry.main.name
}

output "acr_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "gateway_hmac_secret" {
  value     = random_password.gateway_hmac_secret.result
  sensitive = true
}

output "key_vault_uri" {
  value = azurerm_key_vault.main.vault_uri
}

output "azure_managed_grafana_endpoint" {
  value = azurerm_dashboard_grafana.main.endpoint
}

output "action_group_id" {
  value = azurerm_monitor_action_group.alerts.id
}

