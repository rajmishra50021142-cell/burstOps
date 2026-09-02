# Upgrade C — the cost model, its assumptions, how to reconcile

## The model (gateway/costing.py — pure, stdlib-only, golden-vector tested)

Two list-price functions mirror Azure Functions Consumption billing:

- `kubernetes_cost_per_request()` — amortized node cost. **Sunk**, but needed
  for the comparison; the k8s counter series is an *amortization*, not an
  incremental charge.
- `serverless_cost_per_request(duration_s)` — per-execution + per-GB-second,
  with the two billing rules people routinely miss:
  1. **100 ms minimum billable duration** (a 30 ms invocation bills as 100 ms).
  2. **Memory rounded UP to 128 MB multiples** of observed usage.

## The honest headline (why there is NO gateway_cost_saved_* metric)

With this project's constants the deflected request costs ~**1.75x more**
at list price than one served on Kubernetes:

| Quantity | Value |
|---|---|
| k8s per request | 2.3111e-07 USD |
| Function @100 ms, 128 MB | 4.0480e-07 USD |
| Premium per deflected request | 1.7369e-07 USD (1.75x) |

The node bill is sunk; deflection adds Function cost on top. What bursting
actually buys, and what the metrics therefore publish:

1. **`gateway_hpa_lag_cost_usd_total`** — the price of the provisioning-lag
   window (first 120 s of each burst episode), when Kubernetes has no
   capacity to sell at any price. This is the metric that answers "was
   BurstOps worth building".
2. **`gateway_burst_premium_usd_total`** — what bursting cost extra, total.
3. **`gateway_breakeven_overflow_rps` = 28.55 rps** — above this sustained
   overflow, adding a node is cheaper than deflecting. Below it,
   per-invocation wins. Caveat: Azure VMs bill per second — for short spikes
   the Function wins regardless, because a node cannot be provisioned fast
   enough to help at all (the entire premise of BurstOps).
4. `gateway_cost_usd_total{route}`, `gateway_cost_per_request_usd{route}`,
   `gateway_assumed_capacity_rps` (surfaces the modelling assumption).

## Verified prices

Azure Functions Consumption list price (centralindia; checked 2026-09-01 via
the Azure Functions pricing page): $0.20 per million executions +
$0.000016 per GB-second. Node: Standard_B2s ≈ $0.0416/hr → $30.37/mo @730h.

**The real invoice is very likely $0**: the Consumption grant gives ~1M
executions + 400k GB-s/month free. The metrics report list price — the right
control-plane signal — but do not tell anyone they spent money they did not
spend.

## Constants (env-overridable via gateway_entrypoint.py)

`EXECUTION_PRICE_USD=2e-07`, `GB_SECOND_PRICE_USD=0.000016`,
`MIN_BILLABLE_SECONDS=0.1`, `FUNCTION_MEMORY_MB=128`,
`NODE_HOURLY_USD=0.0416`, `CLUSTER_CAPACITY_RPS=50`,
`HPA_LAG_WINDOW_SECONDS=120`.

**`CLUSTER_CAPACITY_RPS=50` is a modelling assumption, not a measurement.**
Measure it with a Locust ramp and correct it. At 100 rps the k8s unit cost
halves (1.156e-07) and the premium multiple rises to ~3.5x; breakeven is
unaffected (it divides out).

## Weekly reconciliation against the real bill

Azure Cost Management lags 8–24 h — never wire it to a live panel. Weekly:

```bash
az consumption usage list --start-date <YYYY-MM-DD> --end-date <YYYY-MM-DD> \
  --query "[?contains(instanceName,'burstops')].{name:instanceName,cost:pretaxCost,meter:meterDetails.meterName}" -o table
```

Compare modelled vs actual and record the ratio here. Off by more than ~2x?
The wrong constant is almost always CLUSTER_CAPACITY_RPS or the memory
rounding.

## Live cross-check (measured 2026-09-01, 99 serverless requests)

n=99, sum(latency)=10.55 s → mean 0.1066 s → cost/req 4.183e-07 →
expected 4.141e-05 vs `gateway_cost_usd_total{serverless}` 4.313e-05 —
**4.16% agreement** (per-request durations scatter around the mean; each
billed individually at its own duration).
