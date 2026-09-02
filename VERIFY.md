# BurstOps — Verification Guide

A complete, copy-pasteable walkthrough for verifying every claim of this
project: **locally** (no Azure needed) and **against real Azure** (the live
Function). Every block tells you the exact command, the expected output, and
**what that output proves**.

> Work through it top-to-bottom the first time — each block builds on the
> last. Time needed: ~30 minutes local, +15 with Azure.

---

## Contents

1. [Prerequisites](#0-prerequisites)
2. [Part A — Local verification (no Azure account needed)](#part-a--local-verification)
3. [Part B — Azure verification (live cloud)](#part-b--azure-verification)
4. [Part C — The upgrades (local)](#part-c--the-upgrades-local)
5. [Part D — Reading the results (what each number means)](#part-d--what-each-result-means)
6. [Troubleshooting quick table](#troubleshooting)

---

## 0. Prerequisites

| Tool | Needed for | Check |
|---|---|---|
| Docker Desktop | everything local | `docker info` |
| Python 3.10+ | the test suite | `python3 --version` |
| Azure CLI | Part B only | `az --version` |
| Terraform 1.9+ | Part B cloud-state check | `terraform version` |

**Login once (Part B only):**

```bash
az login
az account show --query name -o tsv     # expect: Azure for Students
```

---

# Part A — Local verification

## A1. The test suite (89 tests — the fastest full check)

**Setup (once):**

```bash
python3 -m venv .venv
.venv/bin/pip install -q pytest pytest-asyncio \
  fastapi uvicorn httpx prometheus-client redis \
  opentelemetry-api opentelemetry-sdk \
  opentelemetry-exporter-otlp-proto-grpc \
  opentelemetry-instrumentation-fastapi \
  opentelemetry-instrumentation-httpx
```

**Run:**

```bash
.venv/bin/pytest tests/ -q
```

**Expect:**

```
89 passed in 0.2s
```

**What it proves — each file pins one subsystem:**

| File | Proves |
|---|---|
| `test_hysteresis.py` (6 tests) | burst exactly at 80, recovery only below 60, dead band 60–80 never flips, no flapping under oscillation, 15 s stale grace, fail-open to BURST. **Never modified by any upgrade** — the original spec holds. |
| `test_hmac_contract.py` (18) | the signing scheme reproduces 4 golden vectors byte-for-byte; wrong key→403, stale/tampered→401, empty-body GET works; **the two `hmac_util.py` copies (dummy-serverless ↔ azure-function) cannot drift apart** |
| `test_proportional_deflection.py` (14) | ratio is 0 in baseline; anti-windup recovers < 0.1 within 30 s; slew limit; integral reset; Bernoulli fidelity; the **closed-loop plant settles at ratio 0.625 and beats binary ~100%** |
| `test_costing.py` (26) | every cost golden vector (100 ms floor, 128 MB rounding, 1.75× premium, 28.55 rps breakeven); no negative/NaN cost; HPA-lag window semantics |
| `test_redis_backplane.py` (10) | CAS leader election (non-holder renew = 0), lease expiry promotion, graceful release, generation guard, Redis-down = degrade not crash, empty REDIS_URL = off |
| `test_tracing.py` (13) | tracing opt-in by default, span shape/parenting, traceparent in/out, **HMAC signature byte-identical with trace headers present**, no credential ever reaches a span, BatchSpanProcessor enforced, `gateway.py` has zero git diff (Upgrade D's defining constraint) |

---

## A2. Bring the stack up

```bash
docker compose up -d --build
sleep 25
docker compose ps --format '{{.Name}}\t{{.Status}}'
```

**Expect:** 10 services, all `Up`, none `Restarting`:

```
burstops-backend-1     Up
burstops-backend-2     Up
burstops-backend-vip   Up
burstops-cadvisor      Up
burstops-cpu-sim-1     Up
burstops-dummy-serverless-1   Up
burstops-gateway-1     Up
burstops-grafana-1     Up
burstops-locust-1      Up
burstops-prometheus-1  Up
```

**What it proves:** the whole architecture builds from scratch and is
healthy — images compile, Prometheus scrapes, nothing crash-loops.

---

## A3. Baseline behaviour — traffic goes to "Kubernetes"

```bash
curl localhost:8080/health
curl localhost:8080/calculate
```

**Expect:**

```json
{"mode":"baseline","last_cpu":20.11}
```
```json
{"source":"k8s","impl":"dummy-backend","hostname":"0e5d2a709ff1",
 "prime_count":168,"prime_sum":76127}
```

**What it proves:**
- `mode: baseline` — the gateway is polling Prometheus successfully (the
  `last_cpu` value is live, near cpu-sim's 20% idle target).
- `source: k8s` + **168 primes / 76127 sum** — the backend does the correct
  real work. If you ever see different numbers anywhere, that component is
  broken.
- Run `/calculate` 6 times — you'll see **two different hostnames**
  alternating: the nginx VIP round-robins across the two "pods", like a real
  Kubernetes Service.

---

## A4. The burst flip — the core of the project

```bash
# 1. saturate the "cluster" (cpu-sim glides from 20% to 95% over 5s)
curl -X POST 'localhost:8002/set?pct=95'

# 2. watch the gateway decide — one line every 3 seconds:
for i in $(seq 1 12); do printf '%02ds  ' $((i*3)); \
  curl -s localhost:8080/health; echo; sleep 3; done
```

**Expect:** `last_cpu` climbs past 80 and the mode flips:

```
15s  {"mode":"baseline","last_cpu":52.9}
24s  {"mode":"baseline","last_cpu":68.9}
30s  {"mode":"burst","last_cpu":80.06}     ← the flip
33s  {"mode":"burst","last_cpu":85.3}
```

```bash
# 3. NOW traffic is deflected, HMAC-signed:
curl localhost:8080/calculate
```

**Expect:**

```json
{"source":"serverless","impl":"dummy-serverless","prime_count":168,
 "prime_sum":76127,"injected_latency_ms":98.5,"cold_start":false}
```

**What it proves — the single most important chain in the project:**
Prometheus query → hysteresis threshold at exactly 80 → route switch →
HMAC signature generated by the untouched `gateway.py` → verified and
accepted by the serverless side → same correct work (168/76127) from the
other tier. `injected_latency_ms` differs per request (the simulated
cold-ish Function).

**Why ~30 s to flip and not instant:** the PromQL uses
`rate(...[30s])` — a 30-second moving window — plus the 5 s glide. The lag
is the measurement's honesty, not a bug.

---

## A5. Hysteresis — recovery strictly below 60

```bash
curl -X POST 'localhost:8002/set?pct=20'
for i in $(seq 1 12); do printf '%02ds  ' $((i*3)); \
  curl -s localhost:8080/health; echo; sleep 3; done
```

**Expect:** mode stays `burst` while CPU is anywhere in 60–80, and only
flips back once it falls *below* 60:

```
18s  {"mode":"burst","last_cpu":60.0005}   ← exactly 60: STILL burst
24s  {"mode":"baseline","last_cpu":54.7}   ← below 60: recovered
```

**Then the dead-band check — a steady 70 must NOT change anything:**

```bash
curl -X POST 'localhost:8002/set?pct=70'; sleep 40
curl -s localhost:8080/health
```

**Expect:** mode unchanged (whatever it was — `baseline` after recovery).

**What it proves:** the dual-threshold design prevents flapping. A single
threshold at 80 would oscillate burst↔baseline forever around the line;
the 60–80 dead band is what kills that.

---

## A6. HMAC rejection — the security contract, live

```bash
sign() { python3 -c "
import hmac,hashlib,sys
ts, body = '$1', '$2'.encode()
print(hmac.new(b'local-dev-secret-change-in-prod', (ts+':').encode()+body, hashlib.sha256).hexdigest())"; }

TS=$(date +%s)
U=http://localhost:8001/calculate        # the local serverless, directly

# 1. correct everything  -> 200
curl -s -o /dev/null -w '%{http_code}\n' "$U" \
  -H "x-functions-key: local-dev-function-key" \
  -H "x-gateway-timestamp: $TS" -H "x-gateway-signature: $(sign $TS '')"

# 2. signature from a different body (tampered)  -> 401
SIG=$(sign $TS '{"n":100}')
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$U" \
  -H "content-type: application/json" -H "x-functions-key: local-dev-function-key" \
  -H "x-gateway-timestamp: $TS" -H "x-gateway-signature: $SIG" -d '{"n":999}'

# 3. timestamp 10 minutes old  -> 401
OLD=$((TS-600))
curl -s -o /dev/null -w '%{http_code}\n' "$U" \
  -H "x-functions-key: local-dev-function-key" \
  -H "x-gateway-timestamp: $OLD" -H "x-gateway-signature: $(sign $OLD '')"

# 4. wrong function key  -> 403
curl -s -o /dev/null -w '%{http_code}\n' "$U" \
  -H "x-functions-key: wrong" -H "x-gateway-timestamp: $TS" \
  -H "x-gateway-signature: $(sign $TS '')"
```

**Expect, in order:** `200`, `401`, `401`, `403`

**What it proves:** defense in depth actually works on the wire — a leaked
key alone is useless (signature), a captured request can't be replayed
(timestamp window ≤ 300 s), and the check order means a wrong-key caller
learns nothing about signature validity.

---

## A7. Metrics + Grafana dashboard

```bash
curl -s localhost:8080/metrics | grep '^# TYPE gateway_' | sort
```

**Expect (22 families):** the 6 original (`routing_mode`,
`cpu_observed_percent`, `prometheus_poll_failures_total`,
`requests_routed_total`, `upstream_latency_seconds`,
`state_transitions_total`) + 3 PI (`deflect_ratio`,
`cpu_setpoint_percent`, `deflect_integral`) + 6 FinOps + 6 backplane + 1
polls-total.

```bash
curl -s localhost:8080/metrics | grep '^gateway_state_transitions_total'
curl -s localhost:8080/metrics | grep '^gateway_requests_routed_total'
```

**Expect:** both directions ≥ 1 (`baseline_to_burst` and
`burst_to_baseline`) and both routes counted — the system demonstrably
made real routing decisions.

**Dashboard:** open **http://localhost:3000** (admin / burstops), the
"BurstOps — Burst Routing Monitor" dashboard with 12 panels rendering live
data. Key panels during an A4 burst: *Routing Mode* flips 0→1; *Requests
Routed by Destination* shows the green (k8s) line stop and orange
(serverless) line start; *Deflection Ratio* climbs slew-limited toward 1.0;
the *FinOps* row accrues.

**What it proves:** the metric names are the contract — unchanged through
four upgrades — and Grafana resolves them without manual setup (the
provisioned `burstops-prometheus` datasource).

---

## A8. Grafana datasource health (the subtle Phase-0 trap)

```bash
curl -s -u admin:burstops -X POST \
  http://localhost:3000/api/datasources/uid/burstops-prometheus/health
```

**Expect:**

```json
{"status":"OK","message":"Successfully queried the Prometheus API.",...}
```

**What it proves:** the datasource with uid `burstops-prometheus` (which
every panel is hardcoded to) exists and can actually query Prometheus. This
was the classic silent failure of the original repo — a dashboard that
loads with six "datasource not found" panels.

---

---

# Part B — Azure verification

The cloud side is **one live Azure Function** (Flex Consumption,
centralindia) + storage + capped telemetry, all inside free grants.
Verification covers: it exists, it enforces auth, it accepts our signed
requests, and the **local gateway can route real traffic to it**.

## B1. Cloud state — Terraform is idempotent

```bash
cd terraform
export ARM_SUBSCRIPTION_ID=$(az account show --query id -o tsv)
terraform plan
```

**Expect:**

```
No changes. Your infrastructure matches the configuration.
```

**What it proves:** everything in Azure matches the code exactly — no
drift, no surprise resources billing.

**Inventory check:**

```bash
az resource list -g rg-burstops-prod --query "[].{name:name,type:type}" -o table
```

**Expect exactly:** the storage account, the App Insights component, the
Log Analytics workspace, the Function App's service plan + site, and the
"Application Insights Smart Detection" rule. **No VMs, no AKS, no ACR, no
Key Vault, no public IPs** — the free-tier architecture is what's actually
deployed.

## B2. The Function is alive and enforcing auth

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  https://func-burstops-cvkzqc.azurewebsites.net/api/calculate
```

**Expect: `401`**

**What it proves:** 401 (not 404/503) = the app is deployed, running, and
the platform is rejecting unsigned traffic at `AuthLevel.FUNCTION` *before
our code runs*. A 404 would mean the route is wrong; a 503 would mean the
host is down.

## B3. Retrieve the two secrets (never printed to logs)

```bash
# the function key — generated by Azure, never stored in Terraform state
KEY=$(az functionapp keys list -g rg-burstops-prod -n func-burstops-cvkzqc \
      --query 'functionKeys.default' -o tsv)

# the HMAC secret — Terraform-generated; read from local state
SECRET=$(python3 -c "
import json
for r in json.load(open('terraform.tfstate'))['resources']:
    if r['type']=='random_password':
        print(r['instances'][0]['attributes']['result']); break")
```

## B4. The six-case HMAC contract against REAL Azure

```bash
signaz() { python3 -c "
import hmac,hashlib
print(hmac.new('$SECRET'.encode(),('$1:').encode()+'$2'.encode(),hashlib.sha256).hexdigest())"; }
code() { curl -s -o /tmp/b -w '%{http_code}' --max-time 60 "$@"; echo "  <- $(head -c 120 /tmp/b)"; }
U=https://func-burstops-cvkzqc.azurewebsites.net/api/calculate
TS=$(date +%s)

echo "1. valid GET:";    code "$U" -H "x-functions-key: $KEY" \
  -H "x-gateway-timestamp: $TS" -H "x-gateway-signature: $(signaz $TS '')"

echo "2. valid POST:";  SIG=$(signaz $TS '{"n":100}'); \
  code -X POST "$U" -H "content-type: application/json" -H "x-functions-key: $KEY" \
  -H "x-gateway-timestamp: $TS" -H "x-gateway-signature: $SIG" -d '{"n":100}'

echo "3. tampered body:"; \
  code -X POST "$U" -H "content-type: application/json" -H "x-functions-key: $KEY" \
  -H "x-gateway-timestamp: $TS" -H "x-gateway-signature: $SIG" -d '{"n":999}'

echo "4. stale timestamp:"; OLD=$((TS-600)); \
  code "$U" -H "x-functions-key: $KEY" \
  -H "x-gateway-timestamp: $OLD" -H "x-gateway-signature: $(signaz $OLD '')"

echo "5. wrong key:";  code "$U" -H "x-functions-key: wrong" \
  -H "x-gateway-timestamp: $TS" -H "x-gateway-signature: $(signaz $TS '')"

echo "6. no headers:"; code "$U"
```

**Expect:**

```
1. valid GET:    200  <- {"source": "serverless", "impl": "azure-function", "instance_id": "...", "prime_count": 168, "prime_sum": 76127, ...
2. valid POST:   200  <- same shape
3. tampered body:401  <- {"detail": "invalid signature"}
4. stale:        401  <- {"detail": "stale timestamp"}
5. wrong key:    401  <- (platform rejects before our code runs)
6. no headers:   401
```

**What it proves:** the exact same crypto contract verified locally (A6)
holds against real Azure infrastructure — the code deployed to
`azure-function/` is provably the same logic, and Microsoft's platform and
our verifier agree on what "rejected" means. Case 1's body proves the real
Function does the correct work (168/76127) with `impl: "azure-function"`.

**Latency probe (optional but instructive):**

```bash
for i in 1 2 3 4 5; do curl -s -o /dev/null -w '%{time_total}s\n' --max-time 60 \
  "$U" -H "x-functions-key: $KEY" -H "x-gateway-timestamp: $TS" \
  -H "x-gateway-signature: $(signaz $TS '')"; done
```

**Expect:** first hit ~1.0–1.5 s (cold start — a real Flex instance
spinning up), then ~0.13–0.20 s warm. **What it signifies:** the honest
latency cost of the serverless tier from your laptop to centralindia —
compare against the dummy's constant 50–150 ms and the K8s path's ~5 ms.

## B5. End-to-end: local gateway → REAL Azure Function

This is the project's headline proof. **`.env` is never edited** — an
overlay redirects the gateway:

```bash
cd ..   # repo root
# put the real key into .env.azure (gitignored):
python3 -c "
key = '$KEY'
s = open('.env.azure').read()
import re
s = re.sub(r'FUNCTION_KEY=.*', 'FUNCTION_KEY='+key, s)
open('.env.azure','w').write(s)
print('key injected')"

# restart ONLY the gateway with the overlay:
docker compose --env-file .env --env-file .env.azure up -d --force-recreate gateway
sleep 12

# verify baseline still works locally:
curl localhost:8080/calculate     # "source":"k8s"

# trigger a burst and route through REAL Azure:
curl -X POST 'localhost:8002/set?pct=95'
sleep 35
curl localhost:8080/health        # "mode":"burst"
curl --max-time 60 localhost:8080/calculate
```

**Expect:**

```json
{"source":"serverless","impl":"azure-function","instance_id":"...",
 "prime_count":168,"prime_sum":76127,"cold_start":false}
```

```bash
# and the gateway counted it on the serverless route:
curl -s localhost:8080/metrics | grep '^gateway_requests_routed_total'
curl -s localhost:8080/metrics | grep '^gateway_upstream_latency_seconds_count'

# restore the offline default:
curl -X POST 'localhost:8002/set?pct=20'
docker compose up -d --force-recreate gateway     # plain .env again
```

**What it proves — the complete system on real infrastructure:** a request
entered your laptop's gateway, the hysteresis machine decided `burst`, the
untouched `gateway.py` signed it, it crossed the internet to a real Azure
Flex Consumption Function, was verified, executed, and returned the same
168/76127 through the gateway. `impl: "azure-function"` is the marker that
this was Azure and not the local dummy. The latency histogram now carries
real end-to-end serverless timings.

## B6. The budget guardrail

```bash
az consumption budget list -o table 2>/dev/null || \
  az consumption budget show --budget-name budget-burstops -g "" -o table 2>/dev/null || \
  az resource list -g rg-burstops-prod --query "[?contains(type,'budget')].name" -o tsv
```

**Expect:** `budget-burstops`, amount 50, monthly grain, alerts at
50/80/100% to your email. **What it proves:** even if something unexpected
happened in Azure, you'd get an email long before any real money.

## B7. Telemetry is capped under the free grant

```bash
az resource show -g rg-burstops-prod -n appi-burstops-cvkzqc \
  --resource-type "Microsoft.Insights/components" \
  --query 'properties.{cap:dailyCapInGb}' -o json
```

**Expect:** cap ≈ 0.15 GB/day. **What it proves:** 0.15 × 31 ≈ 4.65 GB/mo
— mathematically inside the always-free 5 GB/mo grant, so telemetry can
never bill even if something runs away.

---

# Part C — The upgrades (local)

## C1. Upgrade A — PI proportional deflection

```bash
curl -s localhost:8080/metrics | grep -E '^gateway_(deflect_ratio|cpu_setpoint)'
# baseline: gateway_deflect_ratio 0.0  |  gateway_cpu_setpoint_percent 75.0

curl -X POST 'localhost:8002/set?pct=85'    # hold ABOVE the setpoint, below... just above burst
sleep 40
for i in $(seq 1 8); do printf '%02ds  ' $((i*5)); \
  curl -s localhost:8080/metrics | grep -E '^gateway_(deflect_ratio|cpu_observed_percent)' | tr '\n' ' '; echo; sleep 5; done
```

**Expect:** ratio 0 until burst; then a **slew-limited climb** — no 5 s
interval jumps by more than 0.5 — heading toward 1.0 (cpu-sim ignores
deflection, so full saturation against a deaf plant is the *correct*
open-loop behaviour, not a failure).

**Traffic genuinely splits mid-climb:**

```bash
for i in $(seq 1 200); do curl -s -o /dev/null localhost:8080/calculate; done
curl -s localhost:8080/metrics | grep '^gateway_requests_routed_total'
# BOTH route labels incremented simultaneously — the headline visual

curl -X POST 'localhost:8002/set?pct=20'   # recovery
sleep 30
curl -s localhost:8080/metrics | grep -E '^gateway_(deflect_ratio|deflect_integral)'
# ratio AND integral back to 0 within ~30 s (anti-windup proven live)
```

## C2. Upgrade B — 3 replicas, leader election, failover

```bash
docker compose down    # the base stack maps a fixed port; start clean
docker compose -f docker-compose.yml -f docker-compose.scale.yml up -d --build --scale gateway=3
sleep 30

# exactly one leader; polls climb on ONE pod only:
for i in 1 2 3; do P=$(docker compose -f docker-compose.yml -f docker-compose.scale.yml \
   port --index=$i gateway 8080 | cut -d: -f2); \
  echo "replica $i:"; curl -s http://localhost:$P/metrics | \
  grep -E '^gateway_(is_leader|prometheus_polls_total)'; done
```

**Expect:** exactly one `gateway_is_leader 1.0` (sum = 1 across replicas);
`gateway_prometheus_polls_total` climbing on that one only, `0.0` on the
others — one poller, N routers.

**Failover — kill the leader and time the handover:**

```bash
# find the leader container, delete it, and watch a follower take over:
LEADER=$(for c in $(docker ps --format '{{.Names}}' | grep gateway); do \
  docker exec $c python3 -c "
import urllib.request as u
m=u.urlopen('http://localhost:8080/metrics').read().decode()
print('$c') if 'gateway_is_leader 1.0' in m else None" 2>/dev/null; done)
echo "leader: $LEADER"
date +%s; docker rm -f "$LEADER" >/dev/null
# poll the survivors until is_leader 1 reappears (expect ≤ 8s; measured 4s)
```

**Redis outage = graceful degradation:**

```bash
docker stop burstops-redis
sleep 20
# every gateway: redis_up 0, error counters climbing, polls resume LOCALLY,
# requests still 200, zero restarts:
docker ps --format '{{.Names}} {{.Status}}' | grep gateway
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:$(docker compose \
  -f docker-compose.yml -f docker-compose.scale.yml port --index=1 gateway 8080 | cut -d: -f2)/calculate
docker start burstops-redis; sleep 20    # one leader re-elected automatically

# back to normal:
docker compose -f docker-compose.yml -f docker-compose.scale.yml down
docker compose up -d
```

## C3. Upgrade C — FinOps numbers

```bash
curl -s localhost:8080/metrics | grep -E '^gateway_(breakeven|cost_per_request|assumed_capacity)'
```

**Expect:**

```
gateway_breakeven_overflow_rps 28.546...    ← ≈ 28.5 rps
gateway_cost_per_request_usd{route="k8s"} 2.311...e-07
gateway_cost_per_request_usd{route="serverless"} 4.048e-07   ← the 1.75× premium
gateway_assumed_capacity_rps 50.0            ← the modelling assumption, surfaced not hidden
```

Drive some traffic in both modes and watch `gateway_cost_usd_total`,
`gateway_burst_premium_usd_total` and `gateway_hpa_lag_cost_usd_total`
accrue on the correct route labels — the FinOps row in Grafana renders the
same series. **The 1.75× premium is the honest headline: bursting costs
more per request at list price; what it buys is availability during HPA
lag** — which is exactly what `gateway_hpa_lag_cost_usd_total` prices.

## C4. Upgrade D — tracing in Jaeger

```bash
docker compose -f docker-compose.yml -f docker-compose.tracing.yml up -d --build gateway jaeger
sleep 30
for i in $(seq 1 20); do curl -s -o /dev/null localhost:8080/calculate; done   # baseline traces
curl -X POST 'localhost:8002/set?pct=95'; sleep 35
for i in $(seq 1 15); do curl -s -o /dev/null --max-time 10 localhost:8080/calculate; done
open http://localhost:16686       # Service: burstops-gateway → Find Traces
```

**What to look for in a burst trace:**

| Span | Attributes |
|---|---|
| `GET /calculate` (server) | `burstops.routing_mode=burst`, `burstops.cpu_observed_percent≈91`, `burstops.deflect_ratio≈0.8`, `burstops.route=serverless` |
| `GET` (client, child) | `burstops.route=serverless` — the signed call to the serverless tier |

```bash
# verify the HMAC path was untouched by tracing (zero signature failures):
docker compose logs dummy-serverless | grep -icE 'rejected|40[13]' || echo 0

curl -X POST 'localhost:8002/set?pct=20'
docker compose up -d --force-recreate gateway    # back to default (tracing off)
```

**What it proves:** one waterfall shows the routing decision, the chosen
upstream, and the per-request latency split — and (pinned by tests)
`traceparent` headers ride along *outside* the signed payload, so the
signature stays byte-identical with tracing on.

---

# Part D — What each result means

| Observation | Significance |
|---|---|
| mode flips at exactly 80.0 | threshold logic is spec-exact, not "roughly 80" |
| flip takes ~30 s from ramp | the 30 s `rate()` window + 5 s glide — measurement honesty |
| recovery only below 60 (not at 79) | hysteresis dead band works; no flapping |
| 70% steady changes nothing | the band is stable in BOTH directions |
| 168 / 76127 everywhere | every tier does identical correct work — the canary |
| `401/403` in the right order | key first, then timestamp, then signature — no information leak to attackers |
| both `route` labels increment at once | proportional deflection is real, not all-or-nothing |
| ratio climbs ≤ 0.5 per 5 s | slew limiting — the controller acts slower than the plant, by design |
| integral back to 0 in < 30 s | anti-windup — no "stuck at 100% deflection" after overload |
| `impl: "azure-function"` via gateway | real Azure accepted a signature from the untouched spec code — the whole thesis |
| cold ≈ 1.1 s, warm ≈ 140 ms | the honest price of the serverless tier; why BurstOps is a shock absorber, not a replacement |
| `is_leader` sums to exactly 1 | no split-brain; the election contract holds |
| failover in ~4 s (bound 8) | lease TTL + one renew interval; leadership is never lost long |
| Redis down → 200s, 0 restarts | the cache is a cache, never a dependency |
| premium 1.75×, breakeven 28.5 rps | the decision numbers: when bursting costs more than scaling out |
| `tfplan` = "No changes" | cloud matches code — no drift, no surprise billing |
| budget $50 + cap 0.15 GB/day | belt and braces: even runaway telemetry cannot bill |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `docker compose ps` shows Restarting | image build/entrypoint issue | `docker compose logs <svc>` — most common: none (all pins fixed) |
| `/health` shows `last_cpu` stuck at 0 | Prometheus query returns empty — cpu-sim not scraped | `curl localhost:8002/metrics` and check Prometheus targets at localhost:9090 |
| mode never bursts despite high CPU | rate window lag | wait 30–40 s after `set?pct=95` (A4 explains why) |
| Function URL 503 (B2) | Flex cold stamp warming or host restarting | wait 60–120 s, retry; then `az functionapp restart` |
| B4 case 1 returns 403 `invalid function key` | the `FUNCTION_KEY` app setting doesn't match the real key | re-run B3 and `az functionapp config appsettings set … FUNCTION_KEY=$KEY`, restart, retry |
| B4 case 1 returns 401 `invalid signature` | HMAC secret mismatch (state rotated or read wrong) | re-read SECRET from tfstate (B3); the app setting `GATEWAY_HMAC_SECRET` must equal it |
| B5 gateway still hits dummy | overlay not applied | confirm the recreate command used BOTH `--env-file` flags |
| Grafana panels "datasource not found" | provisioning not mounted | `docker compose restart grafana`; verify `grafana/provisioning/datasources/prometheus.yml` exists |
| 3-replica `port --index` prints `invalid IP:0` | overlay built before the `!override` fix | `docker compose down` then rebuild with the current overlay |
| Jaeger shows no `burstops-gateway` service | tracing env not set / image stale | rebuild with BOTH compose files (C4); check `docker compose logs gateway | grep tracing` |

---

## Quick verification card (print this)

```bash
.venv/bin/pytest tests/ -q                                        # 89 passed
docker compose up -d --build && sleep 25                          # 10 × Up
curl localhost:8080/calculate                                     # k8s, 168/76127
curl -X POST localhost:8002/set?pct=95 && sleep 35                # saturate
curl localhost:8080/calculate                                     # serverless, 168/76127
curl -X POST localhost:8002/set?pct=20                           # recover
terraform -C terraform plan                                       # No changes (az login first)
curl -o /dev/null -w '%{http_code}\n' https://func-burstops-cvkzqc.azurewebsites.net/api/calculate   # 401 = alive + enforcing
```

If all of those return what's expected, **every subsystem of the project is
verified**: state machine, crypto, deflection control, metrics, dashboards,
multi-replica consensus, cost telemetry, tracing, and the real Azure path.
