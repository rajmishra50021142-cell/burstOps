locals {
  common_tags = merge(var.tags, {
    project     = "burstops"
    environment = var.environment
    managed_by  = "terraform"
  })
}

resource "random_string" "suffix" {
  length  = 6
  special = false
  lower   = true
  upper   = false
}

resource "azurerm_resource_group" "main" {
  name     = "rg-burstops-prod"
  location = var.location
  tags     = local.common_tags
}

# --- Storage: required by the Function platform (~$0.05/mo from credit) ----
resource "azurerm_storage_account" "main" {
  name                     = "stburstops${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  tags                     = local.common_tags
}

resource "azurerm_storage_container" "flex_deploy" {
  name                  = "flex-deploy"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

# --- App Insights + Log Analytics (always-free 5 GB/mo grant, capped below) --
resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-burstops-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days
  tags                = local.common_tags
}

resource "azurerm_application_insights" "main" {
  name                 = "appi-burstops-${random_string.suffix.result}"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  workspace_id         = azurerm_log_analytics_workspace.main.id
  application_type     = "other"
  daily_data_cap_in_gb = var.log_daily_cap_gb
  sampling_percentage  = 100
  tags                 = local.common_tags
}

# --- Function hosting: FLEX CONSUMPTION -------------------------------------
# Classic Consumption (Y1) proved broken on this subscription's stamps: the
# host runtime returned 503 ServiceUnavailable in BOTH eastasia and
# centralindia (fresh apps, no code, SCM + API both dead) — a platform-side
# issue, not app-side. Flex Consumption is the current-generation plan with
# a completely different (container-based) deployment path that does not
# depend on the broken Kudu/SCM surface.
resource "azurerm_service_plan" "main" {
  name                = "plan-burstops-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "FC1" # Flex Consumption
  tags                = local.common_tags
}

resource "azurerm_function_app_flex_consumption" "main" {
  name                = "func-burstops-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  service_plan_id             = azurerm_service_plan.main.id
  storage_container_type      = "blobContainer"
  storage_container_endpoint  = azurerm_storage_account.main.primary_blob_endpoint
  storage_authentication_type = "StorageAccountConnectionString"
  storage_access_key          = azurerm_storage_account.main.primary_access_key

  runtime_name    = "python"
  runtime_version = var.python_version

  https_only = true
  # Flex Consumption always runs runtime v4 — no functions_extension_version knob.

  site_config {
    minimum_tls_version                    = "1.2"
    application_insights_connection_string = azurerm_application_insights.main.connection_string
  }

  app_settings = {
    MAX_CLOCK_SKEW_SECONDS = "300"
    # No Key Vault (per-operation billing, no student free tier): the HMAC
    # secret is injected as a plain app setting, encrypted at rest by the
    # platform. Terraform-generated; lives in terraform.tfstate (gitignored,
    # treated as a credential).
    GATEWAY_HMAC_SECRET = random_password.gateway_hmac_secret.result
  }

  identity {
    type = "SystemAssigned"
  }

  tags = local.common_tags
}

# --- Azure Container Registry (ACR) -----------------------------------------
resource "azurerm_container_registry" "main" {
  name                = "acrburstops${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true
  tags                = local.common_tags
}

# --- Azure Kubernetes Service (AKS) -----------------------------------------
resource "azurerm_kubernetes_cluster" "main" {
  name                = "aks-burstops-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  dns_prefix          = "aks-burstops-${random_string.suffix.result}"
  sku_tier            = "Free"

  default_node_pool {
    name                 = "system"
    node_count           = var.node_count
    vm_size              = var.node_vm_size
    os_disk_size_gb      = 32
    auto_scaling_enabled = false
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "kubenet"
    load_balancer_sku = "standard"
  }

  oms_agent {
    log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  }

  tags = local.common_tags
}

resource "azurerm_role_assignment" "aks_acr_pull" {
  principal_id                     = azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id
  role_definition_name             = "AcrPull"
  scope                            = azurerm_container_registry.main.id
  skip_service_principal_aad_check = true
}

data "azurerm_client_config" "current" {}

# --- Azure Key Vault --------------------------------------------------------
resource "azurerm_key_vault" "main" {
  name                        = "kv-burstops-${random_string.suffix.result}"
  location                    = azurerm_resource_group.main.location
  resource_group_name         = azurerm_resource_group.main.name
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  sku_name                    = "standard"
  soft_delete_retention_days  = 90
  purge_protection_enabled    = false
  rbac_authorization_enabled  = false
  tags                        = local.common_tags
}

resource "azurerm_key_vault_secret" "gateway_hmac_secret" {
  name         = "gateway-hmac-secret"
  value        = random_password.gateway_hmac_secret.result
  key_vault_id = azurerm_key_vault.main.id
}

# --- Azure Managed Grafana (PaaS) -------------------------------------------
resource "azurerm_dashboard_grafana" "main" {
  name                              = "amg-burstops-${random_string.suffix.result}"
  resource_group_name               = azurerm_resource_group.main.name
  location                          = azurerm_resource_group.main.location
  grafana_major_version             = 12
  api_key_enabled                   = true
  deterministic_outbound_ip_enabled = false
  public_network_access_enabled     = true
  sku                               = "Standard"
  tags                              = local.common_tags

  identity {
    type = "SystemAssigned"
  }
}

# --- Azure Monitor Alerts & Action Group ------------------------------------
resource "azurerm_monitor_action_group" "alerts" {
  name                = "ag-burstops-alerts"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "burstops"
  tags                = local.common_tags

  email_receiver {
    name          = "Dhruva"
    email_address = "gorkaldhruva@gmail.com"
  }
}

resource "azurerm_monitor_metric_alert" "aks_high_cpu" {
  name                = "alert-aks-high-cpu"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_kubernetes_cluster.main.id]
  description         = "AKS Node CPU exceeded 80 percent - BurstOps burst threshold"
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.common_tags

  criteria {
    metric_namespace = "Microsoft.ContainerService/managedClusters"
    metric_name      = "node_cpu_usage_percentage"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.alerts.id
  }
}

resource "azurerm_monitor_metric_alert" "serverless_deflection" {
  name                = "alert-serverless-deflection"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_function_app_flex_consumption.main.id]
  description         = "BurstOps serverless deflection triggered to Azure Function"
  severity            = 3
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.common_tags

  criteria {
    metric_namespace = "Microsoft.Web/sites"
    metric_name      = "OnDemandFunctionExecutionCount"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 0
  }

  action {
    action_group_id = azurerm_monitor_action_group.alerts.id
  }
}

