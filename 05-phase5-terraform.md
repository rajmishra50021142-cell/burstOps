# PROMPT 05 — Phase 5: Terraform infrastructure, cost-minimized

> Paste this entire file to the coding agent as its task. It is self-contained.

## Your role

You are working on **BurstOps**, a Layer-7 gateway that compensates for
Kubernetes HPA provisioning lag by deflecting overflow traffic to an Azure
Function while cluster CPU is saturated, then returning traffic to Kubernetes
once CPU recovers. It currently runs as a local Docker Compose stack. Phase 4
built a real Azure Function (`azure-function/`). **No Azure resources exist yet.**

This task writes the Terraform that stands up the Azure side. The subscription is
a **cost-minimized (student / free-credit) subscription**, so cheapest-viable SKUs
win over the handoff document's original picks, and every deviation must be called
out rather than made quietly.

**You will actually apply this.** That makes the ordering in §7 mandatory: write,
`validate`, `plan`, show the plan, **stop and wait for explicit approval**, then
apply. Do not run `terraform apply` before that approval.

## Scope

```
terraform/
├── versions.tf          # provider + terraform version pins
├── providers.tf         # azurerm provider config
├── variables.tf
├── main.tf              # RG, ACR, AKS, storage, Function App, Key Vault
├── identity.tf          # managed identities + role assignments
├── budget.tf            # spend guardrail + alert
├── outputs.tf
├── terraform.tfvars.example
├── .gitignore
└── README.md            # apply, retrieve secrets, teardown
```

Splitting into files is additive — the handoff names `terraform/main.tf`, and
everything here still lives under `terraform/`. Note the split in your report.

Do not modify anything outside `terraform/` except appending to the repo-root
`.gitignore` if state files are not already ignored there.

## 1. Verify before you write anything

```bash
terraform version
az account show -o table              # confirm the right subscription
az account list-locations -o table | head -40
az aks get-versions --location <region> -o table
az functionapp list-runtimes --os linux --query "[?runtime=='python']" -o table
az vm list-sizes --location <region> --query "[?name=='Standard_B2s']" -o table
az provider show -n Microsoft.ContainerService --query registrationState -o tsv
grep -rn 'burstopsacr\|burstops' k8s/ | head -20
grep -n 'GATEWAY_HMAC_SECRET\|FUNCTION_KEY\|PROMETHEUS_URL\|K8S_UPSTREAM\|FUNCTION_UPSTREAM' gateway/gateway_entrypoint.py .env
```

Report the subscription name/id (id is fine to show, it is not a secret), the
region you will use, the AKS versions available, and the Python versions offered
for Linux Functions.

**Region default: `centralindia`.** The existing `.env` has
`K8S_UPSTREAM=http://20.219.208.79:8000`, an Azure India address, so that is
likely where earlier experimentation happened, and it keeps latency low for the
operator. Expose it as a variable and confirm the SKUs you need exist there —
free-credit subscriptions sometimes have zero quota in a given region, and
`Standard_B2s` availability in particular varies.

## 2. Provider and version pinning

`versions.tf`:

```hcl
terraform {
  required_version = ">= 1.9.0"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.70" }
    random  = { source = "hashicorp/random",  version = "~> 3.6"  }
  }
}
```

Context you need, because both matter:

- **azurerm 5.0 is generally available**, and 4.70.0 shipped in April 2026. 5.0
  changes resource-provider registration behaviour and adds opt-in preflight
  validation, so it is not a drop-in bump. Pin deliberately: `~> 4.70` is the
  conservative choice with the most existing documentation. If you prefer 5.x,
  read its upgrade guide first and say in your report which you chose and why.
  Whichever you pick, run `terraform init` and record the exact resolved version
  in the README — "latest" is not a pin.
- **`subscription_id` is required in the provider block** from azurerm 4.0 onward.
  It is not a secret, but read it from a variable or `ARM_SUBSCRIPTION_ID` rather
  than hardcoding it in committed HCL.

`providers.tf`:

```hcl
provider "azurerm" {
  subscription_id = var.subscription_id
  features {}
}
```

`features {}` is mandatory even when empty.

**State backend: local, deliberately.** A remote `azurerm` backend needs a storage
account that must exist before Terraform runs, which is a chicken-and-egg problem
not worth solving for a single-operator project. Include the remote backend block
commented out with a note on when to switch. Then treat state as secret material,
because it is: `terraform.tfstate` will contain the generated HMAC secret and
connection strings in plaintext.

`terraform/.gitignore`, and confirm the repo root ignores these too:

```
.terraform/
.terraform.lock.hcl   # or commit it deliberately — say which you chose
*.tfstate
*.tfstate.*
*.tfvars
!*.tfvars.example
crash.log
```

Committing `.terraform.lock.hcl` is normally good practice for reproducibility.
Pick one, do it consistently, explain it in the README.

## 3. Resources, with the cost-minimized choices spelled out

Naming: keep `burstops` everywhere so it matches the Kubernetes namespace
`burstops` and the existing manifests. Resource group **`rg-burstops-prod`**. Use
a `random_string` (lowercase alphanumeric, length 6) suffix for the three
globally-unique names.

| Resource | Terraform type | Cost-minimized config | Rough cost |
|---|---|---|---|
| Resource group | `azurerm_resource_group` | `rg-burstops-prod`, region from var | free |
| Container registry | `azurerm_container_registry` | `sku = "Basic"`, `admin_enabled = false` | ~$5/mo |
| AKS | `azurerm_kubernetes_cluster` | `sku_tier = "Free"`, 1 × `Standard_B2s`, `node_count = 1` | ~$30/mo (nodes only) |
| Storage | `azurerm_storage_account` | `Standard` / `LRS`, TLS 1.2 min, no public blob access | cents |
| Function hosting | see §3b | Flex Consumption or Y1 Consumption | ~free at demo volume |
| Function app | `azurerm_linux_function_app` or flex equivalent | Python, HTTPS-only, FTPS disabled | — |
| Key Vault | `azurerm_key_vault` | `standard`, **RBAC authorization**, soft-delete 7 days | pennies |
| App Insights | `azurerm_application_insights` + `azurerm_log_analytics_workspace` | 30-day retention, **daily cap 0.5 GB** | small, capped |
| Budget | `azurerm_consumption_budget_resource_group` | monthly amount from var, alerts at 50/80/100% | free |

### 3a. AKS — the deliberate deviation

The handoff specifies `Standard_D2s_v5`. **Use `Standard_B2s` instead** (2 vCPU,
4 GiB — the practical floor for a functioning AKS node) with `sku_tier = "Free"`
for the control plane. Roughly half the node cost for a demo cluster.

- Expose `var.node_vm_size` (default `Standard_B2s`) and `var.node_count`
  (default `1`) so this is a one-line change, and **say plainly in the README that
  this deviates from the handoff and why**.
- `os_disk_type = "Managed"`, `os_disk_size_gb = 32`. Do not use `Ephemeral` — B2s
  has too little cache disk for it and the apply will fail.
- Identity: `identity { type = "SystemAssigned" }`.
- `default_node_pool` with `auto_scaling_enabled = false` for predictable cost.
  Argument names around autoscaling changed between azurerm 3.x and 4.x — check
  the docs for your pinned version rather than copying an old snippet.
- **Capacity warning to state explicitly:** one B2s node has ~1.9 allocatable CPU.
  The existing `k8s/backend-deployment.yaml` runs 2 replicas requesting `250m`
  each with `1000m` limits, plus the gateway, plus system pods. That fits, but
  there is little headroom for the HPA scale-out that BurstOps exists to
  compensate for. If the demo needs HPA to visibly add pods, `node_count = 2` is
  the realistic minimum — flag the tradeoff, let the user decide, default to 1.
- No `network_profile` heroics. Default `azure` CNI overlay or `kubenet` per the
  provider default is fine; do not provision an Application Gateway here (see
  Phase 6 — it costs more per month than everything else in this table combined).

### 3b. Function hosting — verify before choosing

The handoff says `azurerm_service_plan` (Consumption) + `azurerm_linux_function_app`.
Since then, **Flex Consumption became the current plan and classic Consumption
(`Y1`) is documented as legacy**. Flex gives faster scaling and lower cold starts,
which is exactly what a burst-deflection demo wants, but it is Linux-only and its
Python version support has historically trailed.

Do this: check what is available (§1's `list-runtimes`, plus the provider docs for
your pinned version — the flex resource is a separate resource type from
`azurerm_linux_function_app`), then pick one and justify it. If Flex is available
with an acceptable Python version, prefer it. If not, use `azurerm_service_plan`
with `os_type = "Linux"`, `sku_name = "Y1"` and note the legacy status.

Either way: `https_only = true`, FTPS disabled, `functions_extension_version = "~4"`,
and the app settings from §4.

### 3c. Naming constraints that will bite you

- **ACR name**: globally unique, alphanumeric only (no hyphens), 5–50 chars →
  `acrburstops${random}`.
- **Storage account**: globally unique, lowercase alphanumeric, 3–24 chars →
  `stburstops${random}`.
- **Key Vault**: globally unique, 3–24 chars, hyphens allowed, cannot start with a
  digit → `kv-burstops-${random}`. Also remember soft-delete means a destroyed
  vault's name is reserved for the retention period — set
  `soft_delete_retention_days = 7` (the minimum) and `purge_protection_enabled = false`
  so teardown-and-recreate cycles actually work. Purge protection cannot be turned
  off once on; enabling it on a demo vault is a trap.
- **Function app**: `func-burstops-${random}`, becomes
  `https://func-burstops-xxxxxx.azurewebsites.net`.

Tag every resource: `project = "burstops"`, `environment = var.environment`,
`managed_by = "terraform"`. Use a `locals.common_tags` map and spread it, so the
budget filter and any later cost queries can group on it.

## 4. Secrets — the part that must be right

**No secret literal may appear in any committed `.tf` or `.tfvars` file.** Not the
HMAC secret, not the function key, not a storage connection string.

The HMAC secret:

```hcl
resource "random_password" "gateway_hmac_secret" {
  length  = 48
  special = false          # keep it header-safe and shell-safe
}

resource "azurerm_key_vault_secret" "gateway_hmac" {
  name         = "gateway-hmac-secret"
  value        = random_password.gateway_hmac_secret.result
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_role_assignment.tf_kv_admin]
}
```

Terraform generates it, Key Vault stores it, nobody types it. Note plainly in the
README that `random_password.result` lands in state in plaintext, which is why
state is gitignored and treated as a credential.

Wire it into the Function App by **Key Vault reference**, not by value:

```hcl
app_settings = {
  GATEWAY_HMAC_SECRET     = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault_secret.gateway_hmac.versionless_id})"
  MAX_CLOCK_SKEW_SECONDS  = "300"
}
```

That requires the Function App to have a system-assigned identity and a
`Key Vault Secrets User` role assignment on the vault. Put both in `identity.tf`.
Use `versionless_id` so rotating the secret does not require a redeploy.

**The env var names are fixed** — `GATEWAY_HMAC_SECRET`, `FUNCTION_KEY`,
`MAX_CLOCK_SKEW_SECONDS`. `azure-function/function_app.py` reads exactly these,
and `gateway/gateway_entrypoint.py` reads the same names on the gateway side. Do
not invent `HMAC_SECRET` or `BURSTOPS_SECRET`.

**The function key: do not manage it in Terraform.** Azure generates host keys.
Reading them via a data source only copies them into state for no benefit.
Document CLI retrieval in the README instead:

```bash
az functionapp keys list -g rg-burstops-prod -n <func-app> --query 'functionKeys.default' -o tsv
```

Also grant AKS pull access to ACR, so Phase 6's deployments need no imagePullSecret:

```hcl
resource "azurerm_role_assignment" "aks_acr_pull" {
  principal_id                     = azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id
  role_definition_name             = "AcrPull"
  scope                            = azurerm_container_registry.main.id
  skip_service_principal_aad_check = true
}
```

Mark every sensitive output `sensitive = true`, and prefer outputting *references*
(vault name, secret name, ACR login server, AKS name, function hostname) over
values.

## 5. `budget.tf` — the guardrail that makes this safe

A free-credit subscription with an AKS cluster left running overnight is the
classic way to burn a month of credit in a week. Add:

```hcl
resource "azurerm_consumption_budget_resource_group" "main" {
  name              = "budget-burstops"
  resource_group_id = azurerm_resource_group.main.id
  amount            = var.monthly_budget_usd     # default 50
  time_grain        = "Monthly"
  time_period { start_date = var.budget_start_date }   # must be first of a month, UTC

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
```

`start_date` must be the first day of a month in UTC and cannot be in the past by
more than the API allows — compute a sane default or make it required, and say
which.

Also put an estimated monthly total in the README, itemized, based on §3's table.
Then state the single most effective cost lever plainly: **`az aks stop`**. Stopping
the cluster halts node billing while preserving cluster state, and it is the right
thing to do between demo sessions.

```bash
az aks stop  --name aks-burstops -g rg-burstops-prod   # stop paying for nodes
az aks start --name aks-burstops -g rg-burstops-prod   # ~3-5 min to resume
```

## 6. `variables.tf` / `terraform.tfvars.example`

Every variable typed, described, and defaulted where a default is safe:

```hcl
subscription_id      # string, required, no default
location             # string, default "centralindia"
environment          # string, default "prod"
node_vm_size         # string, default "Standard_B2s"
node_count           # number, default 1
kubernetes_version   # string, default null -> AKS default; pin once verified
acr_sku              # string, default "Basic"
python_version       # string, default from §1's verification
monthly_budget_usd   # number, default 50
budget_alert_emails  # list(string), required
log_retention_days   # number, default 30
log_daily_cap_gb     # number, default 0.5
tags                 # map(string), default {}
```

`terraform.tfvars.example` shows every one with placeholder values and a comment
saying to copy it to `terraform.tfvars`, which is gitignored.

Add validation blocks where a wrong value costs money — for example reject
`node_count > 3` with a message pointing at the budget, and reject an `acr_sku` of
`Premium`.

## 7. Execution order — this is a hard gate

Run steps 1–5. Then **stop, report, and wait for explicit approval** before step 6.

```bash
cd terraform
terraform fmt -recursive && terraform fmt -check -recursive     # 1
terraform init                                                   # 2
terraform validate                                               # 3
terraform plan -out=tfplan | tee /tmp/plan.txt                   # 4

# 5. secret leak check — must find nothing but Key Vault *references*
terraform show -no-color tfplan | grep -inE 'secret|password|key|token' | grep -v 'Microsoft.KeyVault(SecretUri' | tee /tmp/secretscan.txt
grep -rInE '(secret|password|api[_-]?key)\s*=\s*"[^"$]{8,}' *.tf || echo "no hardcoded secrets in HCL"
git check-ignore -v terraform.tfstate terraform.tfvars .terraform || echo "WARNING: state/tfvars not ignored"

# ---- STOP HERE. Post the plan summary and wait for approval. ----

terraform apply tfplan                                           # 6, only after approval
terraform plan                                                   # 7, must report "No changes"
```

Step 7 is the idempotency check and it is not optional — a plan that still shows
changes right after apply means something is misconfigured (a common culprit is
app settings Azure rewrites server-side, which then need `lifecycle { ignore_changes }`).

### Post-apply verification

```bash
az aks get-credentials -g rg-burstops-prod -n aks-burstops --overwrite-existing
kubectl get nodes -o wide
kubectl version --short
az acr login -n <acr-name> && az acr repository list -n <acr-name>   # empty is correct
az keyvault secret show --vault-name <kv> -n gateway-hmac-secret --query 'id' -o tsv
curl -sS -o /dev/null -w '%{http_code}\n' https://<func-app>.azurewebsites.net/api/calculate  # 401 = alive and enforcing auth
az consumption budget list -o table 2>/dev/null || az consumption budget show --budget-name budget-burstops -o table
```

A **401** from the Function URL with no headers is the correct, healthy answer: the
app is deployed and rejecting unsigned traffic. A 404 means the route or function
name is wrong; a 503 means the app is not running.

### Teardown

The README must document both:

```bash
az aks stop --name aks-burstops -g rg-burstops-prod   # pause node billing, keep everything
terraform destroy                                      # remove everything
```

For `destroy`, list what survives: Key Vault soft-delete holds the vault name for
the retention window, and Log Analytics workspaces have their own soft delete.
Include the `az keyvault purge` command needed to reuse the name immediately.

## 8. Stop and ask — do not decide these yourself

- **Never run `terraform apply` before the §7 gate.** Show the plan, wait.
- The plan would create anything not in §3's table — especially an Application
  Gateway, a Premium ACR, a Standard/Premium Redis, a NAT Gateway, or more than
  `var.node_count` nodes. Any of those materially changes the bill.
- `Standard_B2s` has no quota in the chosen region, or the subscription's vCPU
  quota is below what the plan needs. Report the quota error and the options
  (different region, different SKU, quota increase request) rather than silently
  upsizing.
- Flex Consumption is unavailable or lacks the Python version Phase 4 targeted.
- You want to deviate from the `burstops` naming or the `rg-burstops-prod` resource
  group name, which the existing `k8s/` manifests and namespace assume.
- The provider version you resolve is 5.x and the upgrade guide flags a breaking
  change affecting these resources.
- Anything would require editing files outside `terraform/`.

## 9. Report back with

1. §1's verification output: subscription, region, AKS versions, Python runtimes,
   B2s availability.
2. The provider version you pinned and resolved, and the 4.x-vs-5.x reasoning.
3. Every file, in full.
4. `fmt`/`validate` output, and the **full plan summary** (resource count by
   action, plus the itemized list).
5. The secret-scan results from §7 step 5 — explicitly confirm the only matches
   are `@Microsoft.KeyVault(SecretUri=...)` references.
6. The itemized monthly cost estimate and the budget you set.
7. Every deviation from the handoff document, each with a one-line reason. At
   minimum: node SKU (`B2s` vs `D2s_v5`), the file split, the hosting-plan choice,
   and Key Vault / App Insights / budget being additions the handoff did not list.
8. **Then stop and wait.** After approval: apply output, the post-apply
   verification results, and the teardown commands with the exact resource names
   filled in.

Do not write Kubernetes manifests, build images, or touch the gateway. Phase 6 is
a separate task with its own brief.






