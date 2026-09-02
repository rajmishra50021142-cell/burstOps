# PROMPT 09 — Upgrade C: FinOps telemetry (cost per routing decision)

> Paste this entire file to the coding agent as its task. It is self-contained.

## Your role

You are working on **BurstOps**, a Layer-7 gateway that compensates for
Kubernetes HPA provisioning lag. When cluster CPU crosses 80% it deflects traffic to
an Azure Function; below 60% it returns traffic to Kubernetes. It exposes six
`gateway_*` Prometheus metrics and a 6-panel Grafana dashboard.

This task attaches **money** to every routing decision, so the dashboard can answer
"what did bursting cost, and what did it buy" instead of only "where did traffic go".

## 1. Read this section before writing any code — the accounting is the hard part

The obvious framing is "deflecting to serverless saves money". **At the margin, that
is false**, and shipping a dashboard that claims it would be worse than shipping
nothing.

The AKS node bill is **sunk**. You pay for `Standard_B2s` whether it serves 0 or
50 requests per second. Deflecting a request to the Function does not refund a cent
of node cost — it *adds* Function cost on top. With this project's own numbers
(§3), a deflected request costs about **1.75× more** than one served on Kubernetes.

So what does bursting actually buy? Three things, and each maps to a number you can
publish:

1. **Availability during provisioning lag.** HPA needs tens of seconds to minutes to
   add capacity; a new node needs longer. During that window there is no Kubernetes
   capacity to buy at any price, so the Function is not the expensive option — it is
   the only option. The honest metric is therefore "what did the lag window cost",
   not "what did we save".
2. **Avoided scale-out.** If overflow is small and short, paying per-invocation beats
   provisioning a whole node. If overflow is large and sustained, the node wins. That
   crossover is computable (§4) and belongs on the dashboard as a live number.
3. **Avoided SLO breach.** Not directly monetizable here. Mention it, don't fake a
   number for it.

Everything below follows from that. **Do not publish a metric named
`gateway_cost_saved_*`.** If you find yourself wanting one, re-read this section.

## 2. Scope

```
gateway/
├── costing.py            # new — pure functions, stdlib only, no I/O
├── gateway.py            # surgical: record cost after each upstream call
└── gateway_entrypoint.py # new env vars patched in
tests/
└── test_costing.py       # new
grafana/provisioning/dashboards/burstops.json   # + one "FinOps" row
docs/
└── upgrade-c-cost-model.md   # the model, its assumptions, and how to reconcile it
```

Do not modify `tests/test_hysteresis.py`, `tests/test_proportional_deflection.py`,
`tests/test_redis_backplane.py`, `.env`, `docker-compose.yml`, `dummy-serverless/`,
`azure-function/`, or `k8s/backend-*.yaml`.

`costing.py` being pure and stdlib-only is deliberate: it makes the whole model
unit-testable without FastAPI, Prometheus, or Azure, exactly like
`dummy-serverless/hmac_util.py`.

## 3. The cost model

Two functions, both pure:

```python
def kubernetes_cost_per_request(node_hourly_usd: float, capacity_rps: float) -> float:
    """Amortized node cost. Sunk, but needed for the comparison."""
    return node_hourly_usd / (3600.0 * capacity_rps)


def serverless_cost_per_request(duration_s: float, memory_mb: float = 128.0) -> float:
    """Azure Functions Consumption list price: per execution + per GB-second."""
    billable_mb  = 128.0 * math.ceil(memory_mb / 128.0)       # rounded up
    billable_s   = max(duration_s, MIN_BILLABLE_SECONDS)       # 0.1 floor
    return EXECUTION_PRICE_USD + (billable_mb / 1000.0) * billable_s * GB_SECOND_PRICE_USD
```

Two billing rules that materially change the number and that people routinely miss:

- **Minimum billable duration is 100 ms.** A 30 ms invocation bills as 100 ms. On the
  serverless burst path most requests are short, so ignoring this understates cost by
  a factor of three.
- **Memory is rounded up to the nearest 128 MB** of *observed* usage, not configured
  usage. 128 MB is the realistic floor for a Python worker.

Also note, and put it in the docs rather than in the metric: the Consumption plan
includes a monthly free grant (on the order of 1M executions and 400,000 GB-seconds).
At demo volumes the **actual invoice is very likely $0**. The metric reports list
price, which is the right thing for a control-plane signal — but do not tell the user
they spent money they did not spend.

### Verify these prices, then keep the vectors

Prices vary by region and change. Check `centralindia` on the Azure Functions and
Linux VM pricing pages, or with `az vm list-skus` plus the retail prices API, and
record what you found with the date. Then keep the model's constants as follows —
**these exact numbers are what the golden vectors in §6 depend on**:

| Constant | Default | Env var |
|---|---|---|
| `EXECUTION_PRICE_USD` | `0.20 / 1e6` | `EXECUTION_PRICE_USD` |
| `GB_SECOND_PRICE_USD` | `0.000016` | `GB_SECOND_PRICE_USD` |
| `MIN_BILLABLE_SECONDS` | `0.1` | `MIN_BILLABLE_SECONDS` |
| `FUNCTION_MEMORY_MB` | `128.0` | `FUNCTION_MEMORY_MB` |
| `NODE_HOURLY_USD` | `0.0416` | `NODE_HOURLY_USD` |
| `CLUSTER_CAPACITY_RPS` | `50.0` | `CLUSTER_CAPACITY_RPS` |
| `HPA_LAG_WINDOW_SECONDS` | `120.0` | `HPA_LAG_WINDOW_SECONDS` |

`NODE_HOURLY_USD = 0.0416` is one `Standard_B2s` (≈ $30.37/month at 730 hours),
matching Phase 5's cost table. `CLUSTER_CAPACITY_RPS = 50.0` is the assumed
saturation throughput of the two backend replicas — it is a **modelling assumption,
not a measurement**. Measure it with a Locust ramp and correct it, then say what you
measured.

### The results this produces

| Quantity | Value |
|---|---|
| Kubernetes, per request | `2.311111e-07` USD |
| Function, 100 ms, 128 MB | `4.048000e-07` USD |
| Function, 50 ms (floored to 100 ms) | `4.048000e-07` USD |
| Function, 150 ms | `5.072000e-07` USD |
| Premium per deflected request | `1.736889e-07` USD (**1.75×**) |

So bursting costs roughly 75% more per request than serving on the cluster. That is
the headline, and it is the opposite of what a naive FinOps panel would claim.

## 4. The breakeven — the number that makes this an actual FinOps tool

At what sustained overflow rate does adding a node become cheaper than deflecting?

```
breakeven_rps = NODE_HOURLY_USD / (3600 * serverless_cost_per_request(d))
```

With the defaults at 100 ms: **28.55 requests/second**. Below that, per-invocation
billing is the cheaper way to absorb overflow. Above it, you are paying more than a
whole extra node costs and should scale the cluster instead.

Publish it as a gauge and put it on the dashboard next to the *current* overflow
rate. Two lines crossing is a decision, and it is far more useful than a cumulative
dollar total nobody acts on.

```python
def breakeven_overflow_rps(node_hourly_usd, duration_s, memory_mb) -> float: ...
```

Caveat to state in the docs: Azure VMs bill per second, so a node used for five
minutes costs five minutes — the breakeven above assumes *sustained* overflow. For
short spikes the Function wins regardless, because the node cannot be provisioned
fast enough to help at all. Which is, of course, the entire premise of BurstOps.

## 5. Metrics — six new, none renamed

| Metric | Type | Meaning |
|---|---|---|
| `gateway_cost_usd_total{route="k8s"\|"serverless"}` | Counter | list-price spend attributed per route |
| `gateway_burst_premium_usd_total` | Counter | `(serverless − k8s)` per deflected request; what bursting cost extra |
| `gateway_hpa_lag_cost_usd_total` | Counter | premium accrued in the first `HPA_LAG_WINDOW_SECONDS` of each burst episode — the price of provisioning lag |
| `gateway_breakeven_overflow_rps` | Gauge | §4 |
| `gateway_cost_per_request_usd{route}` | Gauge | current unit cost, for sanity-checking the model live |
| `gateway_assumed_capacity_rps` | Gauge | surfaces the §3 modelling assumption instead of hiding it |

`gateway_hpa_lag_cost_usd_total` is the metric this upgrade exists for. It is the
one number that answers "was BurstOps worth building": it is the amount of money the
gateway spent covering the window in which Kubernetes had no capacity to sell.

Implementation notes:

- Record cost **after** the upstream call returns, using the **observed** duration you
  already measure for `gateway_upstream_latency_seconds`. Do not use a nominal value —
  the whole point is that the real duration drives the bill.
- `prometheus_client` `Counter.inc()` accepts floats, so tiny increments are fine.
  **Never put money in a Histogram** and never use a Gauge for a cumulative total;
  both break `rate()` and `increase()`.
- Amounts are ~1e-7. Counters are float64, so precision is a non-issue at these
  magnitudes, but say so in the docs before someone "fixes" it with integer cents.
- Attribute k8s cost per request even though it is sunk — that is what makes the two
  series comparable. Say clearly in the docs that the k8s series is an *amortization*,
  not an incremental charge.
- Detect burst-episode start from the existing `gateway_state_transitions_total` path
  or a timestamp set on entry to `BURST`; accrue into
  `gateway_hpa_lag_cost_usd_total` only while `now - burst_started < HPA_LAG_WINDOW_SECONDS`.

### Reconciling with the real bill

Azure Cost Management data lags roughly 8–24 hours, so it cannot drive a live panel —
do not try. Instead document a weekly reconciliation:

```bash
az consumption usage list --start-date <YYYY-MM-DD> --end-date <YYYY-MM-DD> \
  --query "[?contains(instanceName,'burstops')].{name:instanceName,cost:pretaxCost,meter:meterDetails.meterName}" -o table
```

Compare the modelled total against actuals and record the ratio in
`docs/upgrade-c-cost-model.md`. If the model is off by more than ~2×, the wrong
constant is almost always `CLUSTER_CAPACITY_RPS` or the memory rounding.

## 6. `tests/test_costing.py` — golden vectors

These values are computed from §3's constants and are correct as printed. Assert them
literally, so any change to the model or the billing rules fails loudly:

```python
# raw linear model, no 100ms floor applied — memory 128 MB
RAW = [
    (0.00, 2.000000e-07),
    (0.03, 2.614400e-07),
    (0.05, 3.024000e-07),
    (0.10, 4.048000e-07),
    (0.15, 5.072000e-07),
    (0.25, 7.120000e-07),
    (1.00, 2.248000e-06),
]
# with the 100 ms minimum applied — everything below 0.1 collapses to one value
BILLED = [
    (0.00, 4.048000e-07),
    (0.03, 4.048000e-07),
    (0.05, 4.048000e-07),
    (0.10, 4.048000e-07),
    (0.15, 5.072000e-07),
    (1.00, 2.248000e-06),
]
K8S_PER_REQUEST   = 2.311111111111111e-07     # 0.0416 / (3600 * 50)
PREMIUM_AT_100MS  = 1.7368888888888893e-07
BREAKEVEN_RPS     = 28.54633289415898
```

Expose both `serverless_cost_per_request_raw()` (linear, no floor) and
`serverless_cost_per_request()` (floor + memory rounding) so the two tables above are
each directly testable. Use `pytest.approx(..., rel=1e-9)`.

Required cases:

1. All seven `RAW` vectors and all six `BILLED` vectors, exactly.
2. `K8S_PER_REQUEST`, `PREMIUM_AT_100MS`, `BREAKEVEN_RPS`, exactly.
3. **The premium is positive** at the default constants. Assert it explicitly — this
   is the counterintuitive result from §1 and a test is the right place to pin it.
4. Memory rounding: 100 MB, 128 MB and 200 MB bill as 128, 128 and 256 respectively.
5. Non-negativity and monotonicity in duration across 0 → 60 s.
6. Zero and negative durations do not produce negative or `NaN` cost.
7. `capacity_rps = 0` raises rather than dividing by zero.
8. **Attribution over a simulated stream**: 10,000 requests at `deflect_ratio = 0.625`
   with durations drawn from a fixed seed produce
   `gateway_cost_usd_total{route="serverless"}` within 1% of
   `6250 * serverless_cost_per_request(mean_duration)`, and the k8s series within 1%
   of `3750 * K8S_PER_REQUEST`.
9. **Counter monotonicity**: over that stream, no cost counter ever decreases.
10. HPA-lag window: requests deflected at `t = 30s` into a burst accrue into
    `gateway_hpa_lag_cost_usd_total`; requests at `t = 200s` do not.
11. All earlier test files still pass, unmodified.

## 7. Grafana — one new row, existing panels stay put

Add a **"FinOps"** row below whatever panels already exist — six in the shipped
dashboard, seven if Upgrade A has landed and added its Deflection Ratio panel. Do not
renumber, reorder, or reformat any of them, and every new panel's datasource uid must be
`burstops-prometheus` or it renders "datasource not found".

Suggested panels and queries:

- **Spend rate, USD/hour, by route** — `rate(gateway_cost_usd_total[5m]) * 3600`
- **Cost this range, by route** — `increase(gateway_cost_usd_total[$__range])`
- **Burst premium, cumulative** — `increase(gateway_burst_premium_usd_total[$__range])`
- **Cost of HPA lag (stat, big number)** — `increase(gateway_hpa_lag_cost_usd_total[$__range])`
- **Breakeven vs actual overflow** — `gateway_breakeven_overflow_rps` overlaid with
  `rate(gateway_requests_routed_total{route="serverless"}[1m])`. This is the panel a
  human actually uses; put it first in the row.

Set the unit to `currencyUSD` with 6 decimal places. At demo volumes the totals are
fractions of a cent, and a panel showing `$0.00` for everything teaches nobody
anything.

## 8. Acceptance

```bash
pytest tests/ -q
docker compose up -d --build
sleep 25

# A. the new metric names exist, with the right types, and nothing was renamed
curl -s localhost:8080/metrics | grep -E '^# (HELP|TYPE) gateway_(cost|burst_premium|hpa_lag|breakeven|assumed)' 
curl -s localhost:8080/metrics | grep -E '^gateway_' | grep -v '^#' | sort
# all six original names must still be present, byte-identical

# B. baseline traffic accrues k8s cost only
for i in $(seq 1 100); do curl -s -o /dev/null localhost:8080/calculate; done
curl -s localhost:8080/metrics | grep -E 'gateway_cost_usd_total|gateway_cost_per_request_usd'
# expect route="k8s" climbing, route="serverless" at 0

# C. burst traffic accrues serverless cost and premium
curl -sX POST localhost:8002/ramp-up; sleep 35
for i in $(seq 1 100); do curl -s -o /dev/null localhost:8080/calculate; done
curl -s localhost:8080/metrics | grep -E 'gateway_cost_usd_total|gateway_burst_premium_usd_total|gateway_hpa_lag_cost_usd_total'

# D. cross-check the model against the counters by hand
#    serverless_requests * serverless_cost_per_request(observed_p50) should match
#    gateway_cost_usd_total{route="serverless"} to within a few percent. Show the arithmetic.
curl -s localhost:8080/metrics | grep -E 'gateway_requests_routed_total|gateway_upstream_latency_seconds_(sum|count)'

# E. breakeven gauge is sane and reacts to constants
curl -s localhost:8080/metrics | grep gateway_breakeven_overflow_rps    # ~28.5 at defaults

curl -sX POST localhost:8002/ramp-down
```

Pass criteria: every original metric name unchanged; cost accrues to the correct route
label in both modes; the hand cross-check in D agrees with the counters within a few
percent (state the numbers); `gateway_breakeven_overflow_rps` reads ≈ 28.5;
`pytest tests/ -q` green with all earlier test files unmodified; the Grafana FinOps
row renders with no "datasource not found".

## 9. Stop and ask — do not decide these yourself

- **You want to publish a "cost saved" metric.** Re-read §1. If you still believe
  there is a defensible saved-cost number, write the argument down and wait.
- Hardcoding prices you did not verify, or changing the §3 constants — the §6 golden
  vectors depend on them, so a constant change means a vectors change means a
  deliberate decision.
- Wiring in the Azure Cost Management / retail prices API as a live dependency. The
  data lags a day, and adding an outbound API call to the request path or the poll
  loop is a latency and failure-mode regression. Weekly reconciliation only.
- Renaming, relabelling, or reordering any of the six existing metrics, or touching
  the six existing Grafana panels.
- Modifying any existing test file.
- Changing routing behaviour. This upgrade **observes**; it must not influence which
  upstream is chosen. If you want cost-aware routing — deflect only while under
  breakeven, for instance — that is a genuinely interesting follow-up and a different
  design. Propose it, don't build it.
- `CLUSTER_CAPACITY_RPS` turns out to be badly wrong when you measure it. Report the
  measurement and the effect on every published number.

## 10. Report back with

1. The prices you verified, where from, for which region, and on what date.
2. `costing.py` in full, and unified diffs for `gateway.py` /
   `gateway_entrypoint.py`.
3. `pytest tests/ -q` output and the new test file in full.
4. The §3 results table recomputed from your code, so the vectors are confirmed rather
   than copied.
5. §8's A–E output, including the hand cross-check arithmetic from D.
6. The measured `CLUSTER_CAPACITY_RPS` if you measured it, and what changed.
7. A short, plainly-worded paragraph on what the dashboard now says: the premium
   multiple, the breakeven rps, the observed cost of HPA lag for one burst episode,
   and the note that the real invoice is likely $0 under the free grant.
8. `git diff --stat` confirming the protected files are untouched.

Do not implement tracing. That is Upgrade D.




