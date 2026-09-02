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

# ARCHITECTURE DECISION (Option B, 2026-09-01): no AKS cluster, no ACR, no
# Load Balancer, no public IP. The subscription is region-locked by policy
# to 5 regions and none offers a free-grant VM SKU meeting AKS's minimum
# node spec. The local Docker Compose stack IS the cluster; this Function is
# the live burst target. Full reasoning in docs/architecture-decision.md.
