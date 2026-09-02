# PROMPT 03 — Phase 0c: build `cpu-sim/` and get the whole stack green

> Paste this entire file to the coding agent as its task. It is self-contained.

## Your role

You are working on **BurstOps**, a Layer-7 gateway that compensates for
Kubernetes HPA provisioning lag by deflecting overflow traffic to a serverless
upstream while CPU is saturated. It runs locally as a Docker Compose stack.

This task builds the last missing piece, `cpu-sim/`, and then proves the whole
stack works end to end. After this, `docker compose up --build` must succeed and
the burst behaviour must be demonstrable on demand.

## Why `cpu-sim` exists

The gateway decides when to burst by running exactly this PromQL every 2 seconds:

```promql
avg(rate(container_cpu_usage_seconds_total{namespace="burstops"}[30s])) * 100
```

That is supposed to be fed by cAdvisor. But on Docker Desktop, cAdvisor runs in
restricted mode and only publishes aggregate `/`, `/docker` and `/restricted`
metrics — never per-container series. So the label set the query needs never
appears, the query returns empty, and the gateway can never see a CPU spike.

`cpu-sim` is a small service that publishes `container_cpu_usage_seconds_total`
in exactly the shape that query expects, with control endpoints to ramp the
simulated load up and down. `docker-compose.yml` already declares it (built from
`./cpu-sim`, port `8002`, env `INITIAL_CPU_PCT`) and
`prometheus/prometheus.yml` already scrapes it as job `cpu-sim` at
`cpu-sim:8002/metrics`. **The directory does not exist.** Build it.

## Scope

```
cpu-sim/
├── app.py
├── requirements.txt
├── Dockerfile
└── .dockerignore
```

Do not modify `gateway/`, `prometheus/prometheus.yml`, `docker-compose.yml`,
`.env`, `grafana/`, `tests/`, `dummy-backend/`, or `dummy-serverless/`. §7 lists
the things you must flag instead of fixing.

## 1. Verify before you write anything

```bash
ls -la cpu-sim/ 2>&1                    # expect: does not exist
grep -n -E 'PROM_QUERY|PROMETHEUS_URL|POLL_INTERVAL|BURST_THRESHOLD|RECOVERY_THRESHOLD|STALE_STATE_GRACE|FAIL_OPEN' gateway/gateway.py
grep -n -A 30 'cpu-sim' prometheus/prometheus.yml
grep -n -B2 -A 20 'cpu.sim' docker-compose.yml
grep -n -A 25 'job_name.*cadvisor' prometheus/prometheus.yml
docker compose config --services | tee /tmp/services.txt; wc -l < /tmp/services.txt
```

Report: the exact `PROM_QUERY` string, the four threshold/timing constants, the
`cpu-sim` scrape job block, and the real service count (the handoff says 9, but
the service map appears to list 10 once both backend replicas are counted — state
what `docker compose config --services` actually returns).

## 2. The metric math — get this exactly right

The query is `avg(rate(counter[30s])) * 100`. There is no `by` clause, so `avg`
collapses **every** series matching `{namespace="burstops"}` into one number.

Therefore: if you publish N series and each one increases at `r` core-seconds per
wall-clock second, `rate()` is `r` for each, `avg` is `r`, and the query reports
`r * 100`. To make the gateway observe 85, every series must accrue **0.85 per
second**. That is the whole contract.

Consequences to design around:

- The counter is in **core-seconds**, not percent. 1.0 means one core fully busy.
  A target of 85 means 0.85 cores. This is why `docker-compose.yml` caps the real
  backend replicas at `cpus: "1.0"` — with a 0.3 cap the metric could never
  numerically reach 80.
- Publish **2 series** to mimic the two backend replicas, with label values
  matching the real container names (`burstops-backend-1`, `burstops-backend-2`)
  so the data looks like what cAdvisor would produce. Since `avg` ignores series
  count, both must accrue at the same rate to hit the target — do not split the
  target between them.
- The counter must be **monotonically non-decreasing**. Only ever `inc()`. Never
  set, never reset, never decrease when the target drops — a lower target means a
  *slower* rate of increase, not a smaller value. Getting this wrong makes
  `rate()` produce garbage.
- `rate(...[30s])` needs at least two samples in the window; Prometheus scrapes
  every 2s, so that is satisfied a few seconds after startup. But the 30s window
  also means a step change in target takes up to ~30s to be fully reflected.
  Expect a burst transition roughly 10–30s after a ramp-up, not instantly. Say
  so in your report so nobody mistakes the lag for a bug.

### The `prometheus_client` naming trap

`prometheus_client` appends `_total` to counter names. Depending on version it may
also strip a `_total` you supply. So `Counter("container_cpu_usage_seconds_total")`
might expose `container_cpu_usage_seconds_total` (correct) **or**
`container_cpu_usage_seconds_total_total` (silently useless — the query would
match nothing and the gateway would never burst).

Do not reason about which. Implement it, then **verify the exposed name
byte-for-byte**:

```bash
curl -s http://localhost:8002/metrics | grep -E '^container_cpu_usage_seconds'
```

The output must contain lines starting exactly
`container_cpu_usage_seconds_total{` and must contain **no**
`container_cpu_usage_seconds_total_total`. If the suffix doubled, either declare
the counter as `Counter("container_cpu_usage_seconds", ...)` or drop to a custom
collector with `CounterMetricFamily` for exact control. Report which you used and
paste the grep output as proof.

`prometheus_client` also emits a companion `container_cpu_usage_seconds_created`
gauge. Harmless — different metric name, the query cannot match it. Setting
`PROMETHEUS_DISABLE_CREATED_SERIES=true` in the environment suppresses it if you
want cleaner output.

## 3. `cpu-sim/app.py`

FastAPI app named `app`, listening on **8002**. Config from environment:

| Env var | Default | Meaning |
|---|---|---|
| `INITIAL_CPU_PCT` | `20.0` | starting target (name is fixed — compose already sets it) |
| `TICK_SECONDS` | `0.5` | how often the accrual loop advances the counters |
| `RAMP_SECONDS` | `5.0` | time to glide from current to a new target |
| `RAMP_UP_TARGET_PCT` | `95.0` | what `/ramp-up` sets |
| `RAMP_DOWN_TARGET_PCT` | `20.0` | what `/ramp-down` sets |
| `REPLICAS` | `2` | number of simulated containers |
| `NAMESPACE_LABEL` | `burstops` | value of the `namespace` label |
| `PORT` | `8002` | |

Core loop, started as an asyncio task in the FastAPI `lifespan` (same pattern
`gateway.py` uses for its poller):

```python
# Glide current_pct toward target_pct at a bounded rate, then accrue.
async def accrual_loop():
    last = time.monotonic()
    while True:
        await asyncio.sleep(TICK_SECONDS)
        now = time.monotonic()
        dt = now - last          # real elapsed time, never assume TICK_SECONDS
        last = now

        # linear glide: full traverse of the gap takes RAMP_SECONDS
        step = (abs(target_pct - current_pct) / RAMP_SECONDS) * dt if RAMP_SECONDS > 0 else abs(target_pct - current_pct)
        if current_pct < target_pct:
            current_pct = min(target_pct, current_pct + step)
        else:
            current_pct = max(target_pct, current_pct - step)

        core_seconds = (current_pct / 100.0) * dt      # <-- the contract from §2
        for series in counters:
            series.inc(core_seconds)                    # inc only, never set
```

Using measured `dt` rather than the nominal tick matters: under a loaded laptop
the loop drifts, and accruing a nominal 0.5s while 0.9s of wall time passed makes
`rate()` under-report and the burst threshold unreachable.

Endpoints:

| Route | Method | Behaviour |
|---|---|---|
| `/metrics` | GET | Prometheus exposition (`generate_latest`, content type `text/plain; version=0.0.4`) |
| `/health` | GET | `{"status":"ok"}` |
| `/ramp-up` | POST | set target to `RAMP_UP_TARGET_PCT`; accept optional `?target=` and `?seconds=` overrides |
| `/ramp-down` | POST | set target to `RAMP_DOWN_TARGET_PCT`; same optional overrides |
| `/set` | POST | `?pct=<float>` — arbitrary target, clamp to `0..400` and reject non-numerics with 422 |
| `/state` | GET | `{"target_pct","current_pct","replicas","ramp_seconds","cumulative_core_seconds":{...},"uptime_s"}` |

`docker-compose.yml`'s comments reference `curl -X POST http://localhost:8002/ramp-up`,
so `/ramp-up` and `/ramp-down` must be POST and must be spelled exactly that way.

`/state` is what makes this debuggable — when the gateway is not bursting, the
first question is always "what is cpu-sim actually publishing", and `/state` plus
the `/metrics` grep answers it in two commands.

Clamp `/set` above 100 deliberately allowed up to 400: multi-core saturation
(e.g. 250 = 2.5 cores) is a legitimate scenario to test, and the gateway's
threshold logic should handle it.

### Labels

Each of the `REPLICAS` series carries at minimum:

```
container_cpu_usage_seconds_total{namespace="burstops", name="burstops-backend-1"}
container_cpu_usage_seconds_total{namespace="burstops", name="burstops-backend-2"}
```

`namespace="burstops"` is mandatory — it is the only label the gateway's query
filters on. `name` mirrors cAdvisor's container-name label and the container names
`prometheus/prometheus.yml` relabels on. Do not add a `job` label; Prometheus
adds that itself from the scrape config.

Do **not** publish `container_memory_usage_bytes` or `container_spec_cpu_quota`
here. Nothing queries them from this service, and inventing series that look like
cAdvisor's but aren't makes future debugging harder.

## 4. `requirements.txt`, `Dockerfile`, `.dockerignore`

```
fastapi==0.115.5
uvicorn[standard]==0.32.1
prometheus-client==0.21.1
```

Same pins as `gateway/requirements.txt`. Dockerfile mirrors the gateway's
(`python:3.12-slim`, requirements layer first, `EXPOSE 8002`,
`CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8002"]`). `.dockerignore`
as in the other services.

## 5. The cAdvisor overlap — verify, then report, don't fix

On Docker Desktop, cAdvisor's restricted mode means it produces no
`{namespace="burstops"}` series, so `cpu-sim` is the only source and the math in
§2 holds exactly.

On native Linux Docker, cAdvisor **does** produce per-container series, and
`prometheus/prometheus.yml` stamps `namespace="burstops"` onto the two backend
containers. Then both sources match the query, `avg` averages across all of them,
and a real backend sitting near-idle at 0.02 will drag the average down and
suppress bursting even while `cpu-sim` publishes 95.

Determine which situation you are in:

```bash
curl -s 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=container_cpu_usage_seconds_total{namespace="burstops"}' \
  | python3 -m json.tool | grep -E '"job"|"name"|"__name__"' | sort | uniq -c

curl -s 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=count by (job) (container_cpu_usage_seconds_total{namespace="burstops"})' \
  | python3 -m json.tool
```

If series appear under **both** `job="cpu-sim"` and `job="cadvisor"`, say so
explicitly, show the count per job, compute what the dilution does to the
observed value, and propose (but do not apply) the one-line
`metric_relabel_configs` drop rule for the cadvisor job that would fix it.
Changing `prometheus.yml` is a decision for the user, not for you.

## 6. Acceptance — this is the full Phase 0 gate

Two prior tasks created `dummy-backend/Dockerfile` + `requirements.txt`, the
Grafana datasource file, and `dummy-serverless/`. With `cpu-sim/` in place the
entire stack must now come up. Run everything below and paste all output.

```bash
# --- A. Everything builds and starts ---
docker compose build
docker compose up -d
sleep 20
docker compose ps                      # every service Up; none restarting
docker compose config --services | wc -l   # compare against how many are Up

# --- B. cpu-sim publishes the right metric name and shape ---
curl -s http://localhost:8002/metrics | grep -E '^container_cpu_usage_seconds'
curl -s http://localhost:8002/metrics | grep -c 'container_cpu_usage_seconds_total_total' # must be 0
curl -fsS http://localhost:8002/state | python3 -m json.tool

# --- C. Prometheus is scraping every target ---
curl -s http://localhost:9090/api/v1/targets \
  | python3 -c 'import sys,json; [print(t["labels"]["job"], t["health"], t.get("lastError","")) for t in json.load(sys.stdin)["data"]["activeTargets"]]'

# --- D. The gateway's own query returns a number ---
curl -s http://localhost:9090/api/v1/query \
  --data-urlencode 'query=avg(rate(container_cpu_usage_seconds_total{namespace="burstops"}[30s])) * 100' \
  | python3 -m json.tool

# --- E. Baseline state ---
curl -fsS http://localhost:8080/health; echo     # expect mode "baseline"
curl -fsS http://localhost:8080/calculate | python3 -m json.tool   # expect source "k8s"

# --- F. Ramp up and watch the flip ---
curl -fsS -X POST http://localhost:8002/ramp-up; echo
for i in $(seq 1 20); do
  printf '%02ds  ' $((i*3))
  curl -s http://localhost:8080/health
  echo
  sleep 3
done

# --- G. In burst, traffic goes to serverless ---
curl -fsS http://localhost:8080/calculate | python3 -m json.tool   # expect source "serverless"

# --- H. Ramp down and watch it recover ---
curl -fsS -X POST http://localhost:8002/ramp-down; echo
for i in $(seq 1 25); do printf '%02ds  ' $((i*3)); curl -s http://localhost:8080/health; echo; sleep 3; done

# --- I. Hysteresis dead band: 70% must NOT change the mode ---
curl -fsS -X POST 'http://localhost:8002/set?pct=70'; sleep 40
curl -fsS http://localhost:8080/health; echo     # mode must be unchanged from H's end state

# --- J. Gateway metrics all present and moving ---
curl -s http://localhost:8080/metrics | grep -E '^gateway_' | grep -v '^#'

# --- K. Grafana: datasource healthy, dashboard resolves ---
curl -fsS -u admin:burstops -X POST http://localhost:3000/api/datasources/uid/burstops-prometheus/health
curl -fsS -u admin:burstops 'http://localhost:3000/api/search?type=dash-db' | python3 -m json.tool

# --- L. Unit tests still green ---
pytest tests/ -q

# --- M. Load generator reaches the gateway ---
# open http://localhost:8089, start a run at ~20 users, confirm 2xx and that
# gateway_requests_routed_total increments on the expected route label
curl -s http://localhost:8080/metrics | grep gateway_requests_routed_total
```

Pass criteria, every one of them:

- **A** — `docker compose build` succeeds for all services; every service in
  `docker compose ps` is `Up` and none is in a restart loop.
- **B** — exposition contains `container_cpu_usage_seconds_total{` with
  `namespace="burstops"` on 2 series, and zero occurrences of `_total_total`.
- **C** — every scrape target reports `health: "up"`, including `cpu-sim`.
- **D** — the query returns a numeric value close to `INITIAL_CPU_PCT` (default
  20), not an empty result. An empty `result` array here means the label shape is
  wrong and nothing downstream can work.
- **E** — `/health` reports `mode` baseline; `/calculate` returns `source: "k8s"`.
- **F** — `gateway_cpu_observed_percent` climbs and `mode` flips to `burst`
  within ~10–30s of the ramp-up (the 30s `rate()` window plus the 5s glide). State
  the observed time-to-flip.
- **G** — `/calculate` now returns `source: "serverless"`, proving the HMAC
  handshake with `dummy-serverless` works over the real gateway path. This is the
  single most important assertion in this task.
- **H** — mode returns to `baseline` only after observed CPU falls below 60, not
  at 79. State the observed value at the moment of recovery.
- **I** — at a steady 70 the mode does not change. This is the hysteresis dead
  band; a flip here means the state machine is being driven wrongly.
- **J** — all six metrics present: `gateway_routing_mode`,
  `gateway_cpu_observed_percent`, `gateway_prometheus_poll_failures_total`,
  `gateway_requests_routed_total`, `gateway_upstream_latency_seconds`,
  `gateway_state_transitions_total`. `gateway_state_transitions_total` must show
  at least `baseline_to_burst` and the reverse direction with count ≥ 1.
- **K** — datasource health check succeeds; the dashboard
  "BurstOps — Burst Routing Monitor" is listed. Then open
  `http://localhost:3000`, view the dashboard, and confirm **all six panels
  render data with no "datasource not found" error**: Routing Mode, CPU Observed
  vs Thresholds, Requests Routed by Destination, Upstream Latency p95, State
  Transitions, Prometheus Poll Failures. Screenshot or describe each.
- **L** — `pytest tests/ -q` fully green, `tests/test_hysteresis.py` unmodified.
- **M** — Locust drives traffic through the gateway and
  `gateway_requests_routed_total` increments on the `route` label matching the
  current mode.

## 7. Stop and ask — do not decide these yourself

- cAdvisor is also producing `{namespace="burstops"}` series and diluting the
  average (§5). Report and propose; do not edit `prometheus.yml`.
- The gateway never bursts even though §6-D's query returns ≥80. Dump
  `gateway_cpu_observed_percent`, `gateway_prometheus_poll_failures_total`, and
  the gateway logs, and report — do not start editing `gateway.py`.
- `docker-compose.yml` sets `INITIAL_CPU_PCT` to a value that puts the stack in
  burst at startup, or `cpu-sim`'s declared port is not 8002.
- `.env`'s `K8S_UPSTREAM=http://20.219.208.79:8000` is a hardcoded IP rather than
  the portable `http://dummy-backend:8000`. If baseline `/calculate` fails or
  hangs, this is almost certainly why. Flag it, quote both values, and ask before
  changing it — it may be a deliberate test against a remote box.
- Any service needs a `healthcheck` or `depends_on` change to start reliably.

## 8. Report back with

1. The verification output from §1, including the real service count.
2. All four files, in full.
3. Proof of the exposed metric name (the §2 grep output).
4. Every acceptance command's output with a pass/fail line per criterion A–M.
5. Observed time-to-flip on ramp-up, and the CPU value at recovery.
6. A short "how to demo this" note: the exact three commands that take the stack
   from baseline to burst and back.
7. Anything flagged under §7.

Phase 0 is complete when A–M all pass. Do not start Phase 4, Terraform, or any
gateway upgrade — those are separate tasks with their own briefs.





