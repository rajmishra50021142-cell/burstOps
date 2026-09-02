# BurstOps — Coding-Agent Prompt Pack

Ten self-contained prompts covering every piece of work the handoff document
(`burstops-ai-handoff.md`) lists as not yet done. Each file is a complete task
brief: paste the whole file into the coding agent as its instruction. No prompt
assumes the agent has read any other file in this pack, and none assumes the
agent has the handoff document — the contract facts each one needs are restated
inside it.

## Order of execution

Run them in this order. Later prompts depend on artifacts earlier ones create.

| # | File | Scope | Depends on |
|---|---|---|---|
| 01 | `01-phase0a-dummy-backend-build-and-grafana.md` | `dummy-backend/Dockerfile`, `requirements.txt`, Grafana datasource provisioning | — |
| 02 | `02-phase0b-dummy-serverless.md` | `dummy-serverless/` — HMAC verifier + latency injection, port 8001 | 01 |
| 03 | `03-phase0c-cpu-sim-and-acceptance.md` | `cpu-sim/` — synthetic cAdvisor metrics + ramp control, port 8002; full-stack acceptance | 01, 02 |
| 04 | `04-phase4-azure-function.md` | Real Azure Function replacing `dummy-serverless/` | 02 |
| 05 | `05-phase5-terraform.md` | Terraform IaC: RG, AKS, ACR, storage, Function App, Key Vault, budget | 04 |
| 06 | `06-phase6-aks-ingress.md` | AKS manifests, ingress + TLS, ACR image pipeline, in-cluster Prometheus | 05 |
| 07 | `07-upgrade-a-proportional-deflection.md` | Upgrade A — PI controller, continuous deflection ratio | 03 |
| 08 | `08-upgrade-b-redis-backplane.md` | Upgrade B — distributed state, leader election | 06, 07 |
| 09 | `09-upgrade-c-finops-telemetry.md` | Upgrade C — cost model, six cost metrics, Grafana "FinOps" row | 03 |
| 10 | `10-upgrade-d-opentelemetry.md` | Upgrade D — W3C traceparent end-to-end | 03 (04 for full value) |

Prompts 01–03 are Phase 0 and are mandatory before anything else — the stack
does not build today. 07, 09 and 10 only need Phase 0 and can be done locally in
any order relative to each other. 08 genuinely needs multi-replica AKS (06) to
be worth doing, and it should land after 07 so the ratio is part of the state it
replicates.

## The contract every prompt repeats

These five facts are restated in each prompt because breaking any one of them
breaks the system silently rather than loudly:

1. **HMAC scheme.** `signature = HMAC_SHA256(secret, f"{timestamp}:".encode() + body).hexdigest()`,
   sent as `x-gateway-signature` alongside `x-gateway-timestamp` and `x-functions-key`.
2. **Metric names** exposed by the gateway at `/metrics`: `gateway_routing_mode`,
   `gateway_cpu_observed_percent`, `gateway_prometheus_poll_failures_total`,
   `gateway_requests_routed_total{route}`, `gateway_upstream_latency_seconds{route}`,
   `gateway_state_transitions_total{direction}`.
3. **Thresholds.** Burst at CPU ≥ 80.0, recover below 60.0, 15s stale grace, fail
   open to burst. `tests/test_hysteresis.py` asserts six invariants over these.
4. **Ports.** gateway 8080, backend VIP 8000, serverless 8001, cpu-sim 8002,
   cAdvisor 8082, Prometheus 9090, Grafana 3000, Locust 8089.
5. **The entrypoint shim.** `gateway/gateway.py` is read-only spec;
   `gateway/gateway_entrypoint.py` patches its constants from env vars at boot.
   New config goes through the shim, not into `gateway.py`.

## Shared HMAC test vectors

Every prompt that touches signing uses these. They were computed with the
reference formula above and are correct as written — if an implementation
disagrees with them, the implementation is wrong.

```
secret = "local-dev-secret-change-in-prod", timestamp = "1700000000"
  body = b""            -> 7545c853772dd927b78111771008f1ace824d14fd36c02e7c00b301ac3ab933b
  body = b'{"n":100}'   -> 263942c72316a870e757782819c315e543e1653dd9481beae4d6b53abb525d75

secret = "test-secret", timestamp = "1700000000"
  body = b""            -> 0f5d899b28266feacd0515cc219efef93968c602c49ecf488c15da01dba0b4a3
  body = b'{"n":100}'   -> 0bd99a3457b14815fed94d47656212f1a92580d93f8806cf86e67f87642a022b
```

Also fixed and shared: a sieve of Eratosthenes over `2..1000` yields **168
primes summing to 76127**. Both the dummy backend and every serverless
implementation must produce those two numbers.

## Azure assumptions baked into 04–06 and 08

You chose a real deployment on a cost-minimized (student / free-credit)
subscription, so the Azure prompts deviate from the handoff's SKU list in three
places and each prompt says so explicitly and tells the agent to flag it:

- **Node size** — `Standard_B2s` (~$30/mo) with AKS Free-tier control plane,
  instead of the handoff's `Standard_D2s_v5`. Exposed as a Terraform variable.
- **Function hosting** — Flex Consumption is now the current plan and classic
  Consumption (`Y1`) is documented as legacy; the prompt asks the agent to
  verify which is available and to explain the choice before applying.
- **Redis (prompt 08)** — Azure Cache for Redis Basic/Standard/Premium is in
  retirement, with creation blocked for tenants that had no instance before
  April 2026 and full retirement in September 2028. The cost-minimized default
  is therefore a single in-cluster Redis pod (no extra Azure spend), with Azure
  Managed Redis as the documented production option.

Every Azure prompt ends with a teardown section and a hard stop before the first
`terraform apply`, so nothing bills without your say-so.

## How to drive the agent

Give it one file, let it finish, read its report, then give it the next. Each
prompt ends with a "report back" section that asks for exactly the information
you need to decide whether to continue. If an agent asks to change
`gateway/gateway.py`, `.env`, `k8s/backend-deployment.yaml`, or
`tests/test_hysteresis.py` outside the prompts that explicitly authorize it, the
answer is no — those are the files the handoff protects.

