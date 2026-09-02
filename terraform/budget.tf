# Spend guardrail. A free-credit subscription with an AKS cluster left
# running overnight is the classic way to burn a month of credit in a week.
resource "azurerm_consumption_budget_resource_group" "main" {
  name              = "budget-burstops"
  resource_group_id = azurerm_resource_group.main.id
  amount            = var.monthly_budget_usd
  time_grain        = "Monthly"

  time_period {
    start_date = var.budget_start_date # first of a month, UTC
  }

  dynamic "notification" {
    for_each = [50, 80, 100]
    content {
      enabled        = true
      threshold      = notification.value
      operator       = "GreaterThan"
      threshold_type = "Actual"
      contact_emails = var.budget_alert_emails
    }
  }
}
