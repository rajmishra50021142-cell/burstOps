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
