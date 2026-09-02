terraform {
  required_version = ">= 1.9.0"

  # State backend: LOCAL, deliberately. A remote azurerm backend needs a
  # storage account that must exist before Terraform runs — chicken-and-egg
  # not worth solving for a single-operator project. Treat terraform.tfstate
  # as SECRET material (it contains the generated HMAC secret in plaintext).
  # To switch later, create the storage account + container and uncomment:
  #
  # backend "azurerm" {
  #   resource_group_name  = "rg-burstops-tfstate"
  #   storage_account_name = "stburstopstfstate"
  #   container_name       = "tfstate"
  #   key                  = "burstops.tfstate"
  # }

  required_providers {
    # azurerm 5.0 is GA but changes provider-registration behaviour and adds
    # opt-in preflight validation — not a drop-in bump. 4.x is the
    # conservative choice with the most existing documentation.
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.70"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
