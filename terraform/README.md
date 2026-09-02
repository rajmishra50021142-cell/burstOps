# BurstOps Terraform (Phase 5) — FREE-TIER architecture, Option B

Every resource is **always-free** except the Function's storage account
(~$0.05/mo, paid from the $100 student credit). **No compute resources at
all** — no AKS, no ACR, no VMs, no Load Balancer, no public IP.

## What exists and what it costs

| Resource | SKU / tier | Why free | Bill |
|---|---|---|---|
| Resource group `rg-burstops-prod` (eastasia) | — | free | $0 |
| Function App `func-burstops-<rand>` | Consumption (Y1), Python 3.13 | always free: 1M req + 400k GB-s/mo | $0 |
| Storage `stburstops<rand>` | Standard LRS | platform requirement for Functions | **~$0.05/mo (credit)** |
| App Insights + Log Analytics | PerGB2018 | always-free 5 GB/mo grant | $0 |
| Telemetry cap | 0.15 GB/day | hard cap < free grant | runaway-proof |
| Budget `budget-burstops` | $50, alerts 50/80/100% | free guardrail | $0 |

**Total: ~$0.05/month, forever. Credit barely touched (~$0.60/year).**

## Architecture decision — Option B (read docs/architecture-decision.md)

The subscription is region-locked by policy to: centralindia, austriaeast,
uaenorth, eastasia, malaysiawest. None offers a free-grant VM SKU that meets
AKS's minimum node spec (>=2 cores, >=4 GB). The cheapest eligible node
(Standard_B2s_v2) would bill ~$30/mo from the $100 credit — rejected.

**So:** the local Docker Compose stack IS the cluster; the real Azure
Function above IS the live burst target. The local gateway points at
`https://func-burstops-<rand>.azurewebsites.net/api/calculate` via the
`.env.azure` overlay (never by editing `.env`). All project logic —
hysteresis, HMAC signing, metrics, dashboards, upgrades — is unchanged.

## Apply

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # fill subscription_id + emails
terraform init
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
terraform plan            # must report "No changes"
```

## Retrieve the function key (never in state/outputs)

```bash
az functionapp keys list -g rg-burstops-prod -n "$(terraform output -raw function_app_name)" \
  --query 'functionKeys.default' -o tsv
```

The HMAC secret is Terraform-generated (`random_password`) and injected as
an app setting — encrypted at rest by the platform, no Key Vault (per-op
billing, no free tier). Plaintext lives in terraform.tfstate: gitignored,
treated as a credential.

## Teardown

Nothing needs scheduled deletion — there is no 12-month cliff because there
are no grant-dependent resources except ACR (already removed) — wait: ACR
was removed in Option B, so NO grant expiry affects this stack. To remove
everything:

```bash
terraform destroy
```

Steady state can be kept indefinitely (~$0.05/mo) — the Function stays live
as the project's serverless target.

## Deviations from the handoff (all deliberate, all cost-driven)

1. **No AKS cluster** — region policy + free-grant SKU limits made a free
   AKS impossible; ~$30/mo alternative rejected. Local Compose is the cluster.
2. **No ACR** — nothing to host without AKS.
3. **No Key Vault** — per-op billing; app setting instead.
4. **eastasia** — one of only 5 policy-allowed regions; southindia 403-blocked.
5. **Python 3.13** — verified via list-runtimes 2026-09-01.
6. **File split** rather than one main.tf — additive, all under terraform/.
