# The gateway's HMAC secret — Terraform generates it, nobody types it.
# Deliberately NO Key Vault: per-operation billing, no student free tier.
# The secret is injected directly as a Function app setting (encrypted at
# rest by the platform). The plaintext lands in terraform.tfstate — state is
# gitignored and treated as a credential.

# The function key: NOT managed in Terraform. Azure generates host keys;
# reading them into state buys nothing. Retrieve via CLI (see README):
#   az functionapp keys list -g rg-burstops-prod -n <func-app> \
#     --query 'functionKeys.default' -o tsv
resource "random_password" "gateway_hmac_secret" {
  length  = 48
  special = false # header-safe and shell-safe
}
