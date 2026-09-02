# BurstOps Architecture Decision — Option B (no AKS cluster)

**Date:** 2026-09-01 · **Status:** decided and implemented · **Decision by:** project owner

## Context

The production handoff planned Phase 6 as a real AKS deployment (Terraform
AKS + ACR, gateway/backend as pods, ingress + TLS). When executing on an
**Azure for Students** subscription with a strict "$0 out of pocket"
constraint, four hard blockers surfaced:

1. **Region lock.** A subscription-level policy
   (`sys.regionrestriction`, created by Microsoft at signup) restricts ALL
   resource deployment to exactly five regions:
   `centralindia, austriaeast, uaenorth, eastasia, malaysiawest`.
   Deploying anything anywhere else returns `403 RequestDisallowedByAzure`.

2. **No free-grant VM can run AKS.** The student free VM grant covers
   `B1s` (1 core), `B2ats_v2` (1 GB) and `B2pts_v2` (1 GB). AKS requires
   nodes with **≥2 cores AND ≥4 GB** (`SystemPoolSkuTooLow`). Every free
   SKU fails at least one requirement — verified via `az vm list-skus` in
   every allowed region.

3. **Cheapest eligible node bills real credit.** `Standard_B2s_v2`
   (2c/8GB, available unrestricted in eastasia) costs ~$30/mo, drawn from
   the $100 credit. Running 24/7 for the planned 5-month project life
   would exceed the credit (~$150) — the subscription would disable around
   month 3. Deleted at month 3 it fits, but leaves ~$5 margin.

4. **(Discovered during deploy attempts) Linux Consumption Functions
   stamps on this subscription returned 503 from the host runtime** in
   both eastasia and centralindia, on fresh empty apps, across SCM and
   API planes — `az functionapp keys list` returned
   `Encountered an error (InternalServerError) from host runtime.`
   This is a platform-side fault, not application-side.

## Decision

**Option B: no AKS, no ACR. The architecture is:**

- **The local Docker Compose stack is the Kubernetes cluster stand-in.**
  dummy-backend (2 replicas + nginx VIP) plays the AKS pods; Prometheus +
  cAdvisor + cpu-sim feed the gateway's exact PromQL unchanged.
- **A real Azure Function (Flex Consumption) in centralindia is the live
  burst target.** Terraform generates the HMAC secret, the function key
  comes from `az functionapp keys list`. The gateway reaches it through
  `FUNCTION_UPSTREAM=https://func-burstops-cvkzqc.../api/calculate`.
- **Hosting plan: Flex Consumption**, created via the az-native path
  (`az functionapp create --flexconsumption-location`) after the
  Terraform-created flex app failed to stamp its runtime config
  (`functionAppConfig: null` → host crash-loop). The az-native app works
  perfectly: ~140 ms warm, ~1.1 s cold, from the operator's laptop.

## What this preserves

Everything the project is actually about:

| Handoff requirement | Option B status |
|---|---|
| Hysteresis 80/60 routing, 15 s grace, fail-open | unchanged, all tests green |
| HMAC signing (gateway) / verification (function) | **proven against real Azure** |
| Six `gateway_*` metrics + 6-panel Grafana dashboard | unchanged |
| Burst deflection to a serverless upstream when CPU ≥ 80 | **proven end-to-end**: local gateway → real Azure Function returning `impl: "azure-function"` |
| IaC for everything cloud-side | Terraform, free-tier only, idempotent |

## What it gives up

- Gateway/backend do not run *inside* Azure Kubernetes Service.
- No ingress controller / TLS termination story (nothing is publicly
  exposed — port-forward only; the gateway has no inbound auth by design).
- Upgrade B (Redis backplane) is demonstrated on the local multi-replica
  overlay instead of AKS pods.

## Cost posture (verified)

| Resource | Bill |
|---|---|
| Function App (Flex Consumption, free grant: 1M req/mo) | $0 |
| Storage account (Function platform requirement) | ~$0.05/mo from credit |
| App Insights + Log Analytics (5 GB/mo always-free, hard-capped at 0.15 GB/day) | $0 |
| Budget guardrail $50, alerts at 50/80/100% | $0 |
| **Total steady state** | **~$0.05/mo** |

No 12-month cliffs exist in the final stack: nothing grant-dependent
remains (ACR was deleted; Functions/telemetry grants are "always free").

## Reversal path

If AKS-on-Azure is ever wanted: create the B2s_v2 node in eastasia
(cheapest eligible), push images to a Standard-tier ACR (free grant for 12
months from creation), and apply the untouched `k8s/` manifests — they
were written for exactly that and remain in the repo.
