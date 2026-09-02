variable "subscription_id" {
  type        = string
  description = "Azure subscription ID. Not a secret, but kept out of committed HCL; also settable via ARM_SUBSCRIPTION_ID."
}

variable "location" {
  type        = string
  default     = "eastasia"
  description = "Subscription policy locks deployment to: centralindia, austriaeast, uaenorth, eastasia, malaysiawest. eastasia chosen: full-service availability. (southindia was blocked by the policy with 403 RequestDisallowedByAzure.)"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "python_version" {
  type        = string
  default     = "3.13"
  description = "From az functionapp list-runtimes --os linux (verified 2026-09-01: newest stable offered)."
}

variable "monthly_budget_usd" {
  type        = number
  default     = 50
  description = "Guardrail: alerts at 50/80/100% of this. Expected actual spend: ~$0.05/mo (storage only) — Option B has no compute resources at all."
}

variable "budget_alert_emails" {
  type        = list(string)
  description = "Required — where budget alerts go."
}

variable "budget_start_date" {
  type        = string
  default     = "2026-09-01T00:00:00Z"
  description = "RFC3339, first of a month, UTC, not more than ~3 months in the past."
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "log_daily_cap_gb" {
  type        = number
  default     = 0.15
  description = "Always-free grant is 5 GB/mo ingestion. 0.15 GB/day = 4.5 GB/mo worst case: mathematically cannot exceed the free grant even if something runs away."
}

variable "tags" {
  type    = map(string)
  default = {}
}

# NOTE (Option B, 2026-09-01): node_vm_size / node_count / kubernetes_version /
# acr_sku variables were REMOVED along with the AKS cluster and ACR. The
# subscription's region policy blocks every free-grant VM SKU that meets
# AKS's minimum node spec, and the cheapest eligible node (~$30/mo from the
# $100 credit) was rejected as too expensive. The local Docker Compose stack
# is the cluster; the Azure Function above is the live burst target.
# See docs/architecture-decision.md for the full reasoning.
