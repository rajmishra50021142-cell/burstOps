# BurstOps — a burst-traffic gateway that buys HPA time

> 📚 **Complete Documentation Guides**:
> - 🏛️ **[Project Architecture & Azure Cloud Reference Manual](file:///Users/rajmishara/burstOps/README_PROJECT_AND_AZURE_ARCHITECTURE.md)** — Complete system architecture, research paper citation, BurstOps Portal walkthrough, Azure Functions deep dive, Azure resources master inventory, and operational CLI commands (`az`, `kubectl`, `terraform`).
> - 🐳 **[Codebase Architecture, Docker Containers & Run Guide](file:///Users/rajmishara/burstOps/README_CODEBASE_AND_CONTAINERS.md)** — Container breakdown, local vs. cloud parity, file-by-file codebase tour, and local execution & testing instructions.

BurstOps is a **Layer-7 traffic gateway** that compensates for Kubernetes
Horizontal Pod Autoscaler (HPA) provisioning lag. HPA needs 30–90+ seconds to
notice a CPU spike, provision pods, and make them ready. BurstOps watches
cluster CPU in real time and, the moment it crosses a threshold, deflects
*overflow* traffic to a serverless upstream (an Azure Function) instead of
letting the existing pods melt. When CPU recovers, traffic returns. It is not
an HPA replacement — it is a **shock absorber** that buys HPA time.

Everything in this repository is **free-tier**: the local demo runs on Docker
with zero cloud spend, and the one always-on cloud resource (the Azure
Function) sits inside Azure's always-free grants. Steady-state cloud bill:
**≈ $0.05/month** (the Function's mandatory storage account, paid from the
student credit — never from pocket).

---

## Table of contents

1. [The 60-second mental model](#the-60-second-mental-model)
2. [Architecture](#architecture)
3. [The wire contract — HMAC](#the-wire-contract--hmac)
4. [The control loop — hysteresis + PI](#the-control-loop--hysteresis--pi)
5. [Observability — metrics, dashboards, tracing](#observability)
6. [FinOps — what bursting actually costs](#finops)
7. [Scale — the Redis backplane](#scale--the-redis-backplane)
8. [The cloud side — Azure free tier](#the-cloud-side)
9. [What we deliberately did NOT use (decision log)](#what-we-deliberately-did-not-use)
10. [Build history — what was executed](#build-history)
11. [How to verify everything](#how-to-verify-everything)
12. [What the numbers signify](#what-the-numbers-signify)
13. [Repository layout](#repository-layout)
14. [Bills, lifecycle, teardown](#bills-lifecycle-teardown)
15. [Honest limitations](#honest-limitations)
16. [Reversal path — real AKS someday](#reversal-path--real-aks-someday)

---

## The 60-second mental model

```
                          ┌────────────────────────────────────────────┐
                          │              BURSTOPS GATEWAY              │
   clients ──/calculate──►│  ┌──────────┐   ┌───────────┐   ┌───────┐  │
                          │  │ poller   │──►│ Routing   │──►│ router│  │
                          │  │ (2s)     │   │ State     │   │ + PI  │  │
                          │  └────┬─────┘   │ 80/60     │   └───┬───┘  │
                          │       │         │ hysteresis│       │      │
                          │       ▼         └───────────┘       ▼      │
                          │  Prometheus query            signed calls  │
                          └───────┼───────────────────────────┬────────┘
                                  │                    CPU < 60 │ CPU ≥ 80
                                  ▼                            ▼
                     avg(rate(container_cpu…[30s]))*100   ┌──────────────┐
                                                          │ Azure Function│
                     ┌────────────────┐                   │ (real, live)  │
                     │  K8s backend   │◄───── baseline ───│ HMAC-verified │
                     │  2 replicas    │                    └──────────────┘
                     └────────────────┘
```

- **CPU < 80%** → every request goes to the Kubernetes-shaped backend.
- **CPU ≥ 80%** → the gateway enters `BURST` and deflects traffic to the
  Function, signing each forwarded request with HMAC-SHA256.
- **CPU falls below 60%** (not 80 — the gap is the anti-flap dead band) →
  back to `BASELINE`.
- In between (60–80%), **nothing changes** — hysteresis in action.

---

## Architecture

### The local "cluster" (Docker Compose — 10 services)

| Service | Image / build | Port | Role |
|---|---|---|---|
| `dummy-backend-1/2` | built from `dummy-backend/` | — | stands in for 2 AKS pods; real CPU work (prime sieve / burn loop); capped at `cpus: 1.0` so the PromQL (cores × 100) can numerically reach 80 |
| `dummy-backend` | `nginx:1.27-alpine` | 8000 | VIP round-robin across the two replicas — simulates a K8s Service |
| `dummy-serverless` | built from `dummy-serverless/` | 8001 | local stand-in for the Azure Function: verifies the exact HMAC contract, injects 50–150 ms latency to feel "cold-ish" |
| `cpu-sim` | built from `cpu-sim/` | 8002 | synthetic cAdvisor: Docker Desktop's cAdvisor is restricted-mode and never publishes per-container series, so cpu-sim publishes `container_cpu_usage_seconds_total{namespace="burstops"}` in exactly the shape the gateway's PromQL expects, with `/ramp-up`, `/ramp-down`, `/set` controls |
| `gateway` | built from `gateway/` | 8080 | **the system** — FastAPI app, background Prometheus poller, hysteresis state machine, PI controller, HMAC signer, Prometheus metrics, tracing hooks |
| `cadvisor` | `gcr.io/cadvisor/cadvisor:v0.49.1` | 8082 | real container metrics (relabel-stamped `namespace="burstops"` for real- Linux use) |
| `prometheus` | `prom/prometheus:v2.53.1` | 9090 | 2s scrape interval; keeps only the backend containers' CPU series for the average |
| `grafana` | `grafana/grafana:11.1.4` | 3000 | auto-provisioned 12-panel dashboard (`burstops-prometheus` datasource) |
| `locust` | `locustio/locust:2.29.1` | 8089 | load generator: 95% GET /calculate through the gateway, 5% /burn-cpu direct at the backend |

**Why this shape:** the gateway's `PROM_QUERY` is
`avg(rate(container_cpu_usage_seconds_total{namespace="burstops"}[30s])) * 100`
— it measures **core-seconds**, i.e. cores × 100, not %-of-quota. That is
why the backend replicas are CPU-capped at 1.0 (a 0.3 cap could never
numerically reach 80), and why averaging across the whole stack would dilute
the signal (hence the Prometheus relabel rules that stamp `namespace`
*only* onto the two backend containers).

### The cloud side (Azure — free tier only)

| Resource | Name | Tier | Cost |
|---|---|---|---|
| Function App | `func-burstops-cvkzqc` | Flex Consumption | $0 (1M req + 400k GB-s/mo free) |
| Storage account | `stburstopscvkzqc` | Standard LRS | ~$0.05/mo (platform requirement) |
| App Insights + Log Analytics | `appi/log-burstops-cvkzqc` | PerGB2018 | $0 (5 GB/mo always-free, hard-capped at 0.15 GB/day) |
| Budget | `budget-burstops` | $50, alerts 50/80/100% | $0 |

The Function is managed by Terraform (`terraform/`), idempotent, and is the
**live burst target**: the local gateway can be pointed at it with a
`.env.azure` overlay without ever editing `.env`.

---

## The wire contract — HMAC

Every deflected request is signed, not just keyed:

```
timestamp = str(int(time.time()))
signature = HMAC_SHA256(GATEWAY_HMAC_SECRET, f"{timestamp}:".encode() + body).hexdigest()
```

sent as three headers: `x-functions-key`, `x-gateway-timestamp`,
`x-gateway-signature`. The Function (and `dummy-serverless`) verify in a
fixed order — key (403), timestamp shape (401), clock skew ≤ 300 s (401),
signature via `hmac.compare_digest` (401) — so a wrong-key caller learns
nothing about signature validity, and a leaked key cannot be replayed past
the 5-minute window. The reference implementation is `gateway.py`'s
`sign_request()`; `dummy-serverless/hmac_util.py` and
`azure-function/hmac_util.py` are **byte-identical copies** (deliberate —
Azure Functions packages one directory; a 60-line duplicated file plus a
test proving the copies agree is cheaper than sys.path hacks), and
`tests/test_hmac_contract.py` pins four golden vectors:

```
secret="local-dev-secret-change-in-prod", ts="1700000000", body=b""
  -> 7545c853772dd927b78111771008f1ace824d14fd36c02e7c00b301ac3ab933b
secret="test-secret", ts="1700000000", body=b'{"n":100}'
  -> 0bd99a3457b14815fed94d47656212f1a92580d93f8806cf86e67f87642a022b   (…4 vectors total)
```

The work function everywhere (K8s and serverless) is a sieve of Eratosthenes
over 2..1000 → **168 primes summing to 76127** — a deliberate canary: any
component returning different numbers is broken.

---

## The control loop — hysteresis + PI

**Layer 1 (spec, untouchable): `RoutingState`.** Burst at ≥ 80, recover
below 60, 15 s stale-poll grace, fail-open to BURST past the grace
(overflowing to serverless is safer than routing blind). Six invariants are
asserted by `tests/test_hysteresis.py` — which was never modified by any
upgrade.

**Layer 2 (Upgrade A): PI proportional deflection.** Binary deflection is
bang-bang control — 100% serverless at 80% CPU collapses the cluster to
idle, 100% back below 60% slams it again: oscillation even with hysteresis.
Instead the gateway holds CPU near a **setpoint (75.0, strictly inside the
60–80 dead band — a setpoint below 60 would make controller and state
machine fight, reintroducing the oscillation one layer up)** by deflecting
a continuously-varying fraction of requests:

- `e = cpu − 75`; `P = 0.04·e`; `I += 0.004·e·dt` (clamped at 1.0)
- **conditional anti-windup**: the integral freezes when the output is
  saturated in the error's direction — without it, two minutes at CPU 100
  winds the integral so far that the controller keeps deflecting 100% of
  traffic for minutes after load drops
- **slew limit 0.10/s**: full 0→1 traverse takes ~10 s, deliberately slower
  than the plant (the 30 s `rate()` window) — stability without careful
  tuning
- **no D term, on purpose**: differentiating a 30 s-smoothed signal
  amplifies scrape noise and buys nothing
- ratio is **0.0 always in BASELINE** and *may legitimately be 0.0 inside
  BURST* (that is how CPU falls far enough to leave BURST)
- realization per request: one `random()` draw vs the ratio (**Bernoulli**
  — stateless, stays correct across N replicas; a deterministic
  every-Nth-request token scheme becomes wrong under multiple replicas)

Measured result (simulated first-order-lag plant, L stepping 0.5C → 2C):
CPU settles at 75 ± 5, ratio settles at **0.625 ± 0.05** (exactly what
L(1−r)/C = 0.75 predicts), and versus binary: **∫|cpu−setpoint|dt 1225.5 →
0.5 (~100% better), peak-to-trough swing 40.8 → 0.1 (99.8%)**.

---

## Observability

**Metrics** (gateway `/metrics`, all six original names byte-identical
through every upgrade):

| Metric | Meaning |
|---|---|
| `gateway_routing_mode` | 0 = baseline, 1 = burst |
| `gateway_cpu_observed_percent` | last CPU seen |
| `gateway_prometheus_poll_failures_total` | poll failures |
| `gateway_requests_routed_total{route}` | k8s vs serverless |
| `gateway_upstream_latency_seconds{route}` | upstream latency histogram |
| `gateway_state_transitions_total{direction}` | every mode flip |
| `gateway_deflect_ratio`, `gateway_cpu_setpoint_percent`, `gateway_deflect_integral` | Upgrade A |
| 6 FinOps metrics | Upgrade C (below) |
| `gateway_is_leader`, `gateway_leader_elections_total`, `gateway_redis_up`, `gateway_redis_errors_total{op}`, `gateway_shared_state_age_seconds`, `gateway_prometheus_polls_total` | Upgrade B |

**Grafana** auto-provisions "BurstOps — Burst Routing Monitor" with 12
panels: the original 6 (Routing Mode, CPU vs Thresholds, Requests by
Destination, Upstream Latency p95, State Transitions, Poll Failures) + the
Deflection Ratio panel + a FinOps row. Every panel's datasource uid is
`burstops-prometheus`.

**Tracing (Upgrade D)** — OpenTelemetry, **zero changes to `gateway.py`**
(test-enforced): instrumentation attaches from `gateway_entrypoint.py` via
`FastAPIInstrumentor` + `HTTPXClientInstrumentor` (including the
already-created module-level client, via async hooks — the sync hook
signature silently does nothing for `AsyncClient`). The exporter is
env-switched — `none` (default: a fresh clone behaves exactly as before),
`console`, `otlp` (local Jaeger via the `docker-compose.tracing.yml`
overlay), `azure_monitor` (in-process exporter; App Insights does not ingest
raw OTLP). Sampling is **routing-aware**: 100% of burst-window traffic, 5%
of baseline — flat head-sampling throws away exactly the rare traces you
want. Spans carry `burstops.routing_mode`, `burstops.route`,
`burstops.cpu_observed_percent`, `burstops.deflect_ratio`; a test scans
every exported attribute for the secret, the key, and the signature —
**no credential ever reaches a span**, and header capture env vars are
never set. W3C `traceparent` rides along freely because headers are outside
the signed payload.

---

## FinOps

The honest accounting (full model in `docs/upgrade-c-cost-model.md`):
**the node bill is sunk** — deflecting a request refunds nothing and *adds*
Function cost. With this project's constants a deflected request costs
**~1.75× more** at list price:

| Quantity | Value |
|---|---|
| k8s per request (amortized B2s) | 2.3111e-07 USD |
| Function @ 100 ms, 128 MB | 4.0480e-07 USD |
| premium per deflected request | 1.7369e-07 USD |
| **breakeven overflow rate** | **28.55 rps** — below it, per-invocation wins; above sustained, a whole node is cheaper |

So there is deliberately **no `gateway_cost_saved_*` metric**. What
bursting buys and what the metrics publish: availability during the HPA
provisioning-lag window (`gateway_hpa_lag_cost_usd_total` — premium accrued
in the first 120 s of each burst episode, the one number that answers "was
BurstOps worth building"), avoided scale-out (the breakeven gauge vs actual
overflow rate), and per-route list-price spend. Azure's Consumption grant
(~1M executions + 400k GB-s/mo) means the real invoice at demo volume is
**$0** — the metrics report list price, the right control-plane signal.
Billing rules people miss, modeled exactly: 100 ms minimum billable duration
and memory rounded up to 128 MB multiples. Live cross-check: 99 serverless
requests, model vs counters agreed within **4.16%**.

---

## Scale — the Redis backplane

`RoutingState` in one process means N replicas = N independent decisions
(split-brain), N× the Prometheus load, and transition metrics multiplied by
N. Upgrade B separates the **control plane** (one poller + state machine +
PI controller) from the **data plane** (N stateless routers):

- Leader election: `SET NX PX 6000`; renewal is a **Lua compare-and-set**
  (check owner + extend atomically) — `SET … XX` would be wrong because XX
  succeeds whenever the key *exists*, never checking *who* owns it, so a
  follower could silently steal a live lease. Graceful release is the same
  CAS pattern → handover in milliseconds, not TTL.
- The leader publishes a state hash with a `generation` counter (INCR);
  followers ignore lower generations (bounds damage from a briefly
  resurrected old leader). Pub/sub notify + 1 s poll backstop.
- **The request path does zero Redis I/O** — followers keep a local cached
  copy; the handler reads memory exactly as before.
- Degradation ladder: fresh shared state → use it; stale/unreadable → poll
  Prometheus yourself (exactly the pre-upgrade single-replica behaviour);
  own polling stale past 15 s → the original fail-open-to-BURST. Redis down
  at startup logs one warning and retries — a gateway that crash-loops over
  a missing cache is worse than no cache.
- Measured live (3 replicas via `docker-compose.scale.yml`): exactly one
  leader, polls climb on one pod only, **leader killed → new leader in 4 s**
  (bound: TTL+renew ≈ 8 s), Redis outage → zero pod restarts, zero failed
  requests, correct routing throughout.

Redis here is unauthenticated **by design**: compose-internal network only,
no persistence, 32 MB LRU — it holds a routing hint any replica can rebuild
in one poll cycle. Azure Cache for Redis was not used (it is in retirement;
the successor starts above the project's entire budget).

---

## The cloud side

`terraform/` (idempotent, `terraform plan` = "No changes") provisions the
free-tier stack: resource group `rg-burstops-prod`, Flex Consumption
Function (Python 3.13, HTTPS-only, FTPS off), its storage account, App
Insights + Log Analytics (capped 0.15 GB/day — mathematically cannot exceed
the always-free 5 GB/mo even if something runs away), and a $50 budget with
50/80/100% alerts. The HMAC secret is `random_password`-generated (nobody
types it, never in committed HCL; it lives in `terraform.tfstate`, which is
gitignored and treated as a credential). The function key is never stored
in Terraform state — retrieved on demand via
`az functionapp keys list … --query 'functionKeys.default'`.

The Function is deployed (`azure-function/`, V2 programming model, single
dependency `azure-functions==1.25.0` — every extra wheel lengthens the cold
start this project measures) and live at
`https://func-burstops-cvkzqc.azurewebsites.net/api/calculate`.

---

## What we deliberately did NOT use

Every exclusion is a cost or correctness decision, documented in
`docs/architecture-decision.md`:

| Rejected | Why |
|---|---|
| **AKS cluster** | The subscription is region-locked by policy to 5 regions (centralindia, austriaeast, uaenorth, eastasia, malaysiawest) — verified via the `sys.regionrestriction` policy assignment. None offers a student free-grant VM SKU (B1s/B2ats_v2/B2pts_v2) that meets AKS's minimum node spec (≥2 cores AND ≥4 GB — every free SKU fails at least one). The cheapest eligible node (~$30/mo) would burn the $100 credit in ~3 months. The local Compose stack is the cluster; the architecture is otherwise identical. |
| **ACR** | Nothing to host without AKS. (It was briefly created in eastasia as the free-grant Standard tier, then deleted when Option B was chosen.) |
| **Key Vault** | Per-operation billing, no student free tier. The HMAC secret is injected as an app setting — encrypted at rest by the platform. |
| **Load Balancer / public IP / Ingress / cert-manager** | Public IPs bill ~$4/mo each and the gateway has **no inbound authentication** — publishing it would expose an unauthenticated prime-sieve + the ability to drive Function invocations on our credits. All demo access is `localhost` / `kubectl port-forward`-style. |
| **Application Gateway** | $130–250/mo fixed — more than every other resource combined would have cost. |
| **Azure Cache for Redis / Managed Redis** | Basic/Standard/Premium in retirement, creation blocked for new tenants; Managed Redis starts above the project's budget. The backplane runs as a plain `redis:7-alpine` container. |
| **PID instead of PI** | The measurement is a 30 s-smoothed average; a D term amplifies scrape noise and buys nothing. |
| **Deterministic token deflection** | Lower variance but shared mutable state — becomes *wrong* with multiple gateway replicas. Bernoulli draws are stateless and aggregate correctly. |
| **A "cost saved" FinOps metric** | At the margin deflection *costs* ~1.75× more (node bill is sunk). A dashboard claiming savings would be worse than none. |
| **OTel packages inside the Azure Function** | Contradicts the single-dependency cold-start rule; App Insights' worker already correlates the invocation with the gateway's trace via the inbound `traceparent` (same `operation_Id`) for free. |
| **`SimpleSpanProcessor`** | Would put exporter network latency inside the request the gateway is measuring. `BatchSpanProcessor` always (test-asserted). |
| **Managed Prometheus / Azure Monitor for metrics** | Billed per ingested sample; self-hosted Prometheus + Grafana is free and matches the local stack exactly. |

Two platform faults were hit and worked around during the build (both
documented in `docs/architecture-decision.md`):

1. **Classic Consumption (Y1) host runtime was broken on this
   subscription** — fresh empty Function Apps returned 503 from the host
   runtime in *both* eastasia and centralindia, across SCM and API planes,
   with `az functionapp keys list` failing with "InternalServerError from
   host runtime". Pivot: **Flex Consumption**, a different (container-based)
   deployment architecture that does not depend on the failing Kudu/SCM
   surface.
2. **Terraform's `azurerm_function_app_flex_consumption` misprovisioned**
   (`functionAppConfig: null` → host crash-loop). The Function was recreated
   via the az-native path (`az functionapp create --flexconsumption-location
   centralindia`) and works perfectly (~140 ms warm, ~1.1 s cold from the
   operator's laptop). Terraform manages everything else; the Function's
   app settings are set via `az functionapp config appsettings`.

---

## Build history

Executed in order from the handoff prompt pack (`00-INDEX.md`):

| Phase | What was delivered | Verified by |
|---|---|---|
| **0a** | `dummy-backend/Dockerfile` + `requirements.txt`, Grafana datasource provisioning (`uid: burstops-prometheus`) | builds clean; round-robin across 2 hostnames; prime count 168 / sum 76127; datasource health OK |
| **0b** | `dummy-serverless/` (hmac_util + FastAPI, port 8001) + `tests/test_hmac_contract.py` | 6/6 live cases (200/200/401/401/403/403), 20 randomized latency samples 50–150 ms, no secrets in logs |
| **0c** | `cpu-sim/` (port 8002) + full-stack acceptance | all A–M: 10 services up, metric name exact (no `_total_total`), all 4 Prometheus targets up, query returns ≈ INITIAL_CPU_PCT, burst flip at ~30 s, recovery at 54.7% (< 60 required), dead band held at 70, all six metrics, dashboard renders, 24 tests green |
| **4** | `azure-function/` (V2 model, verbatim hmac_util port, host.json, tests extended for copy-drift) | local `func start`: 200/200/401/401/403/403; **live Azure**: 200/200/401/401/401/401 with `impl: "azure-function"` |
| **5** | Free-tier Terraform (the saga above) | `terraform plan` = No changes; secret scan clean |
| **6** | End-to-end: local gateway → **real Azure Function** via `.env.azure` overlay (`.env` untouched) | burst triggered → `{"source":"serverless","impl":"azure-function",…}` through the untouched gateway; both transition directions counted |
| **A** | PI controller (surgical additions; `update_from_cpu` byte-identical) | 40 tests incl. closed-loop plant; live slew-limited climb, traffic genuinely split (11 k8s / 289 serverless mid-climb), ratio back to 0 in 25 s; 7th panel |
| **B** | `redis_backplane.py` + scale overlay + fake-Redis tests | 10 tests; live: one leader, polls on one pod, 4 s failover, outage → 0 restarts, 200s throughout |
| **C** | `costing.py` + 6 metrics + FinOps row | 26 golden-vector tests; live cross-check 4.16%; breakeven gauge reads 28.546 |
| **D** | `tracing.py` + Jaeger overlay + tests | 13 tests; live traces in both modes with `burstops.*` attributes; `gateway.py` zero-diff (programmatic guard) |

Final state: **89 tests green**, committed as `1620f88`.

---

## How to verify everything

```bash
# 0. the whole test suite (hysteresis, HMAC incl. cross-copy drift, PI,
#    closed-loop plant, costing golden vectors, backplane CAS, tracing)
python3 -m venv .venv && .venv/bin/pip install -r gateway/requirements.txt pytest pytest-asyncio \
  opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc \
  opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-httpx redis
.venv/bin/pytest tests/ -q          # expect: 89 passed

# 1. the offline stack (dummy-serverless as the burst target)
docker compose up -d --build
curl localhost:8080/health           # {"mode":"baseline",...}
curl localhost:8080/calculate        # source: k8s, 168/76127

# 2. the burst demo — three commands
curl -X POST 'localhost:8002/set?pct=95'   # saturate the "cluster"
sleep 35 && curl localhost:8080/health     # mode: burst
curl localhost:8080/calculate             # source: serverless (HMAC verified)
curl -X POST 'localhost:8002/set?pct=20'  # watch it recover below 60

# 3. dashboards: http://localhost:3000 (admin / burstops)
#    12 panels, live data, no "datasource not found"

# 4. metrics inventory
curl -s localhost:8080/metrics | grep '^# TYPE gateway_'   # 6 original + 3 PI + 6 FinOps + 6 backplane

# 5. the REAL Azure Function end-to end (.env never edited)
az login
KEY=$(az functionapp keys list -g rg-burstops-prod -n func-burstops-cvkzqc \
       --query 'functionKeys.default' -o tsv)
# put KEY into .env.azure (gitignored), then:
docker compose --env-file .env --env-file .env.azure up -d --force-recreate gateway
curl -X POST 'localhost:8002/set?pct=95'; sleep 35
curl localhost:8080/calculate          # expect: "impl": "azure-function"

# 6. direct HMAC proof against real Azure (sign the way the gateway does)
TS=$(date +%s)
SECRET="$(retrieve from terraform state / app settings)"
SIG=$(python3 -c "import hmac,hashlib;print(hmac.new('$SECRET'.encode(),('$TS:').encode(),hashlib.sha256).hexdigest())")
curl -s https://func-burstops-cvkzqc.azurewebsites.net/api/calculate \
  -H "x-functions-key: $KEY" -H "x-gateway-timestamp: $TS" -H "x-gateway-signature: $SIG"
# expect 200 + {"source":"serverless","impl":"azure-function",...,"prime_count":168}
# tamper the body / age the timestamp / wrong key -> 401/403

# 7. multi-replica leader election
docker compose -f docker-compose.yml -f docker-compose.scale.yml up -d --build --scale gateway=3
for i in 1 2 3; do
  P=$(docker compose -f docker-compose.yml -f docker-compose.scale.yml port --index=$i gateway 8080)
  curl -s http://$P/metrics | grep -E '^gateway_(is_leader|prometheus_polls_total)'
done
# is_leader sums to exactly 1; polls climb on one pod only

# 8. tracing (Jaeger)
docker compose -f docker-compose.yml -f docker-compose.tracing.yml up -d --build
curl -X POST 'localhost:8002/set?pct=95'; sleep 35
for i in $(seq 1 10); do curl -s -o /dev/null localhost:8080/calculate; done
open http://localhost:16686               # service: burstops-gateway
# burst trace: server span {routing_mode=burst, cpu≈91, deflect_ratio≈0.8,
#              route=serverless} + client child {route=serverless}

# 9. cost model sanity
curl -s localhost:8080/metrics | grep gateway_breakeven_overflow_rps   # ≈ 28.5
curl -s localhost:8080/metrics | grep '^gateway_cost_per_request_usd' # k8s 2.31e-07, serverless 4.05e-07

# 10. cloud state
cd terraform && terraform plan          # "No changes. Your infrastructure matches the configuration."
az consumption budget list -o table     # budget-burstops, $50
```

---

## What the numbers signify

- **Burst flip at ~30 s** after ramp-up = the 30 s `rate()` window + 5 s
  glide — the measurement's own lag, not a bug. Recovery happens only
  **below 60**, never at 79 — hysteresis holding the dead band.
- **`impl: "azure-function"` through the gateway** = a request signed by the
  *unmodified* `gateway.py` was accepted by real Azure infrastructure. That
  is the whole system working end to end: local Prometheus → hysteresis →
  HMAC → Flex Consumption Function → 168/76127 back.
- **Ratio 0.625 at L = 2C** = the controller deflecting exactly the fraction
  the cluster cannot absorb (L(1−r)/C = 0.75 ⇒ r = 0.625). Both route
  labels increment *simultaneously* during partial deflection — the headline
  visual of Upgrade A.
- **Premium 1.75×** = the honest price of the burst path at list price; the
  point of FinOps telemetry is that this is a *decision input* (breakeven
  28.55 rps), not a hidden cost.
- **Failover 4 s** (bound 8 s) and `gateway_prometheus_polls_total` flat on
  followers = one poller, N routers: the N×-load claim made measurable.
- **A trace with `burstops.route=serverless` + `cold_start`** answers a
  question the dashboard cannot: *was that specific slow request a Function
  cold start?*

---

## Repository layout

```
gateway/               the spec + shims
  gateway.py             READ-ONLY spec: state machine, signing, metrics, routes
  gateway_entrypoint.py  env-var shim: patches constants at boot; wires tracing + backplane
  costing.py              pure stdlib cost model (golden-vector tested)
  tracing.py              OTel provider/sampler/hooks (zero gateway.py changes)
  redis_backplane.py      leader election + shared state (Lua CAS)
dummy-backend/         2-replica AKS stand-in + nginx VIP
dummy-serverless/      local Azure Function stand-in (hmac_util is the source of truth)
cpu-sim/               synthetic cAdvisor + ramp controls
azure-function/        the real Function (V2 model; hmac_util verbatim copy)
terraform/             free-tier IaC: Function, storage, telemetry, budget
k8s/                   manifests for the (future) real-AKS path — namespace,
                       backend Deployment (burstops-namespace label), Service
prometheus/ grafana/   scrape config + auto-provisioned 12-panel dashboard
locust/                load profile (95% calculate / 5% burn-cpu)
tests/                 89 tests: hysteresis · HMAC · PI/plant · costing · backplane · tracing
docs/                  architecture-decision · phase6-runbook · cost-model ·
                       tracing notes · backplane notes
docker-compose.yml            offline default
docker-compose.scale.yml      3 gateway replicas + redis (Upgrade B)
docker-compose.tracing.yml    + Jaeger + OTLP (Upgrade D)
.env.azure                    overlay pointing the gateway at the REAL Function
```

---

## Bills, lifecycle, teardown

| Period | What runs | Bill |
|---|---|---|
| Now | Function + storage + telemetry in Azure; local stack on demand | **~$0.05/mo** from credit; $0 pocket |
| Anytime | `docker compose down` | local costs nothing |
| Full exit | `cd terraform && terraform destroy` | $0 thereafter |

There are **no 12-month cliffs** in the final stack — no grant-dependent
resources remain (ACR was deleted; the Function and telemetry grants are
*always-free* tiers). The Function can stay live indefinitely as the
project's serverless target.

---

## Honest limitations

- The local stack is a *stand-in* for AKS (Option B, per
  `docs/architecture-decision.md`): pods are containers, the "Service" is
  nginx, and cpu-sim publishes the cAdvisor series Docker Desktop cannot.
  The architecture, contracts, and logic are unchanged; only the substrate
  is local.
- `cpu-sim` is open-loop: deflecting traffic does not reduce its output, so
  the live PI demo shows the *controller* working (slew-limited climb,
  saturation) against a plant that ignores it — the closed-loop proof lives
  in the simulated-plant test.
- Redis leader election is **not consensus** — a paused leader can briefly
  coexist with a new one (bounded by the generation counter; reconstructible
  in one poll cycle). The correct heavier primitive (a Kubernetes Lease) is
  named, not built.
- Trace headers are unsigned (by design — they're outside the signed
  payload): a caller could graft spans onto your traces. Accepted for an
  internal demo.
- The gateway has **no inbound authentication** — the default deployment is
  localhost-only for exactly this reason. Do not expose it publicly without
  adding auth.
- `CLUSTER_CAPACITY_RPS = 50` is a modelling assumption, not a measurement;
  measure it with a Locust ramp and correct it (it changes the k8s unit cost
  and the premium multiple; breakeven divides out).

---

## Reversal path — real AKS someday

If AKS-on-Azure is ever wanted: the subscription policy allows eastasia,
where `Standard_B2s_v2` (2c/8GB, ~$30/mo) is unrestricted. Push the gateway
and backend images to a Standard-tier ACR (student grant), and apply the
untouched `k8s/` manifests — they were written for exactly that and carry
the `burstops-namespace: burstops` pod label Prometheus's relabel rules
expect. The metric-dilution question (gateway pods inside the same
namespace averaging into the CPU signal) is documented with three options in
the Phase 6 brief — decide it then, not silently.

---

*Built phase-by-phase from the handoff prompt pack (`00-INDEX.md` +
`burstops-ai-handoff (1).md`), every acceptance gate run live, every
cost decision recorded. 89 tests green. Commit `1620f88`.*
