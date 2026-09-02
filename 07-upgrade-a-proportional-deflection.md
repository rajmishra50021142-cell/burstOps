# PROMPT 07 — Upgrade A: proportional deflection (PI control)

> Paste this entire file to the coding agent as its task. It is self-contained.

## Your role

You are working on **BurstOps**, a Layer-7 gateway that compensates for
Kubernetes HPA provisioning lag. A poller queries Prometheus every 2s for cluster
CPU. `RoutingState` is a hysteresis state machine: it enters `BURST` at CPU ≥ 80.0
and returns to `BASELINE` below 60.0, with the 60–80 dead band preventing flapping
and a 15s stale-poll grace period after which it fails open to `BURST`.

Today routing is **binary**: in `BASELINE` every request goes to Kubernetes, in
`BURST` every request goes to the Azure Function. This task makes it
**proportional** — deflect only the fraction of traffic the cluster cannot absorb.

## 1. Why binary deflection is the wrong shape

Walk through what the current design actually does under sustained overload:

1. CPU crosses 80.1 → mode `BURST` → **100%** of traffic leaves Kubernetes.
2. The cluster is now doing nothing. CPU collapses toward idle.
3. CPU drops below 60 → mode `BASELINE` → **100%** of traffic returns at once.
4. The cluster is instantly slammed again. CPU spikes past 80. Go to 1.

The hysteresis band slows this cycle down but does not remove it — this is
bang-bang control, and its steady state is an oscillation between two extremes.
The cluster is never held at a useful utilization, the Function is invoked far more
than necessary (which costs money), and p95 latency sawtooths.

What you want instead is to hold cluster CPU near a **setpoint** by deflecting a
continuously-varying fraction of requests. That is a textbook regulator problem and
the standard answer is a **PI controller**.

## 2. The hard constraint — do not break the state machine

`tests/test_hysteresis.py` must keep passing **unmodified**. It asserts the mode
transitions at 80/60, the dead band, and the stale grace. So:

- **`update_from_cpu()`'s mode arithmetic stays byte-identical.** Do not touch the
  thresholds, the comparison operators, or the stale-grace logic.
- The deflection ratio is a **second, independent layer** on top of the mode, not a
  replacement for it. Add a new method; do not fold the controller into
  `update_from_cpu`.
- Invariants your implementation must hold:
  - `deflect_ratio == 0.0` whenever `mode == BASELINE`. Always. No exceptions.
  - `0.0 <= deflect_ratio <= MAX_DEFLECT_RATIO <= 1.0`.
  - Inside `BURST` the ratio **may legitimately be 0.0**. That is not a bug — it is
    how CPU is allowed to fall far enough for the mode to leave `BURST`.

### The setpoint must sit strictly inside the dead band

This is the part that is easy to get wrong and expensive to debug. Pick a setpoint
of **75.0**, and enforce `RECOVERY_THRESHOLD < CPU_SETPOINT_PERCENT < BURST_THRESHOLD`.

If the setpoint were below 60, the controller and the state machine would fight
each other: the controller drives CPU to 55, the state machine exits `BURST`, exiting
`BURST` forces the ratio to 0, all traffic returns, CPU jumps to 90, the state
machine re-enters `BURST`. That is precisely the oscillation this upgrade exists to
remove, reintroduced one layer up. Add a validation that refuses (or loudly warns
about) a setpoint outside the open interval, and say which behaviour you chose.

### What `BURST` means now — say this in the report

With a setpoint of 75 and a working controller, CPU is *held* at 75, which is above
the recovery threshold, so the gateway **stays in `BURST` for as long as offered
load exceeds cluster capacity**. It leaves `BURST` when real demand drops, not when
the controller succeeds. So the semantics shift: `BURST` used to mean "everything is
going to serverless", and now means "we are actively shedding", with
`gateway_deflect_ratio` telling you how much. Document that — it changes how the
Grafana panels should be read.

## 3. Verify before you write anything

```bash
sed -n '1,240p' gateway/gateway.py
grep -n -E 'class RoutingState|class Mode|def update_from_cpu|BURST_THRESHOLD|RECOVERY_THRESHOLD|STALE_STATE_GRACE|POLL_INTERVAL' gateway/gateway.py
grep -n -A 40 'def update_from_cpu' gateway/gateway.py
grep -n -B3 -A 30 'async def calculate\|api_route.*calculate\|def route_request' gateway/gateway.py
grep -n -E 'Gauge|Counter|Histogram' gateway/gateway.py
cat gateway/gateway_entrypoint.py
cat tests/test_hysteresis.py
grep -c '"panels"\|"id":' grafana/provisioning/dashboards/burstops.json
pytest tests/ -q
```

Report: `update_from_cpu`'s exact current source, the exact names and label sets of
the six existing metrics, the code path that picks the upstream per request, every
env var `gateway_entrypoint.py` already patches, and confirmation that
`pytest tests/ -q` is green **before** you change anything. If it is not green
already, stop — you cannot tell your regressions from pre-existing ones.

## 4. The control law

Run the controller once per poll cycle, using measured elapsed time rather than the
nominal `POLL_INTERVAL`:

```python
e = cpu_observed - CPU_SETPOINT_PERCENT       # >0 means too hot, deflect more
p_term = DEFLECT_KP * e
# integral accrues only when it can actually help (see anti-windup below)
self._integral += DEFLECT_KI * e * dt
self._integral = _clamp(self._integral, 0.0, DEFLECT_INTEGRAL_CLAMP)
raw = p_term + self._integral
target = _clamp(raw, 0.0, MAX_DEFLECT_RATIO)
# slew limit against the previous published ratio
max_step = DEFLECT_MAX_SLEW_PER_SEC * dt
self.deflect_ratio = _clamp(target, self.deflect_ratio - max_step,
                                    self.deflect_ratio + max_step)
```

### Anti-windup is mandatory, not an optimization

Without it: CPU sits at 100 for two minutes, `e` is 25 the whole time, the integral
accumulates far past anything useful, and then when load finally drops the
controller keeps deflecting 100% of traffic for minutes while the integral unwinds.
The cluster sits idle, the Function bill keeps running, and it looks like the
gateway is stuck.

Implement **conditional integration**: skip the integral update when the output is
already saturated in the direction the error is pushing.

```python
saturated_high = raw >= MAX_DEFLECT_RATIO and e > 0
saturated_low  = raw <= 0.0                and e < 0
if not (saturated_high or saturated_low):
    self._integral += DEFLECT_KI * e * dt
```

Also clamp the integral itself, and **reset it to 0.0 on any transition into
`BASELINE`** so a fresh burst starts from a clean state rather than inheriting the
last one's history.

### Why slew limiting, and why no derivative term

The measurement is `avg(rate(...[30s])) * 100`, so what the gateway sees lags
reality by up to 30 seconds, and behind that sits pod-start latency. A controller
allowed to swing 0 → 1.0 in a single 2s tick will act on stale information,
overshoot hard, and ring. Bounding the rate of change is the cheapest way to keep
the loop stable without careful tuning: at `0.10` per second, a full 0 → 1 traverse
takes 10 seconds, which is comfortably slower than the plant.

**Do not add a D term.** Differentiating an already 30s-smoothed signal amplifies
scrape noise and buys nothing here. If a future reader is tempted, the reason it is
a PI and not a PID belongs in a comment next to the constants.

### Constants — module level in `gateway.py`, patched by the shim

| Constant | Default | Env var | Rationale |
|---|---|---|---|
| `CPU_SETPOINT_PERCENT` | `75.0` | same | inside the 60–80 dead band |
| `DEFLECT_KP` | `0.04` | same | `e=5` → 20% deflected; `e=25` (CPU 100) → saturated |
| `DEFLECT_KI` | `0.004` | same | `KP/10`; at steady `e=5` adds ~0.02/s, matching the plant's tens-of-seconds lag |
| `MAX_DEFLECT_RATIO` | `1.0` | same | lower it to keep a floor of traffic on Kubernetes |
| `DEFLECT_MAX_SLEW_PER_SEC` | `0.10` | same | full traverse in ~10s |
| `DEFLECT_INTEGRAL_CLAMP` | `1.0` | same | integral alone can saturate, but no further |

Add each to `gateway_entrypoint.py` using the same patching pattern the existing
env vars use — read the float, set the module attribute. Do not invent a different
mechanism.

## 5. Realizing a fractional ratio per request

```python
if state.mode is Mode.BURST and _rng.random() < state.deflect_ratio:
    upstream = FUNCTION_UPSTREAM   # signed, HMAC path unchanged
else:
    upstream = K8S_UPSTREAM
```

Use **stochastic (Bernoulli) selection**, one `random()` draw per request. It is
stateless, needs no coordination, and stays correct when the gateway is later scaled
to N replicas — each replica independently deflects the same fraction, so the
aggregate is right without any shared counter. The per-request variance is
irrelevant because the quantity being controlled (CPU over a 30s window) is itself
an average.

A deterministic "every Nth request" token scheme has lower variance but introduces
shared mutable state and becomes wrong under multiple replicas. Do not use it.

Details that matter:

- Draw **once** per request and compare once. Two draws compared two ways is a
  subtle bias bug.
- Use a module-level `random.Random()` seeded from the OS, exposed so tests can
  substitute a seeded instance. Under uvicorn's single event loop there is no
  threading concern.
- **The HMAC signing path does not change at all.** A deflected request is signed
  exactly as it is today: `f"{timestamp}:".encode() + body`, headers
  `x-functions-key` / `x-gateway-timestamp` / `x-gateway-signature`. If you find
  yourself touching `sign_request`, you have gone off track.
- `gateway_requests_routed_total{route="k8s"}` and `{route="serverless"}` now
  increment *simultaneously* during partial deflection. That is the headline visual
  payoff — both lines moving at once, in a ratio you can predict.

## 6. Metrics — add three, rename none

Keep all six existing metrics with byte-identical names and label sets;
`grafana/provisioning/dashboards/burstops.json` and every later phase key off them.
Add:

| Metric | Type | Purpose |
|---|---|---|
| `gateway_deflect_ratio` | Gauge | the current fraction, 0.0–1.0 |
| `gateway_cpu_setpoint_percent` | Gauge | so a panel can draw the target line without hardcoding it |
| `gateway_deflect_integral` | Gauge | the integral term, for tuning and for spotting windup |

`gateway_deflect_integral` earns its place: when the controller misbehaves, the first
question is always "is the integral wound up", and a gauge answers it from Grafana
instead of from a debugger.

## 7. `tests/test_proportional_deflection.py` — new file

Do not touch `tests/test_hysteresis.py`. Match its style: import from source, stub
third-party modules rather than requiring the runtime, inject time rather than
sleeping.

Required cases:

1. **Ratio is 0 in `BASELINE`.** Sweep CPU 0→59 and assert `deflect_ratio == 0.0`
   at every step, including immediately after a `BURST` episode ends.
2. **Setpoint validation.** A setpoint of 55 or 85 triggers whichever behaviour you
   implemented (raise or warn) — assert it explicitly.
3. **Monotonicity.** For a fixed state, larger `e` produces a ratio that is greater
   than or equal to the smaller-`e` ratio. Never inverted.
4. **Clamping.** CPU swept 0→400 keeps the ratio inside `[0, MAX_DEFLECT_RATIO]`.
5. **Anti-windup.** Feed CPU 100 for 300 simulated seconds, then drop it to exactly
   the setpoint. Assert the integral never exceeded `DEFLECT_INTEGRAL_CLAMP`, and
   that the ratio returns below 0.1 within **30 simulated seconds** of the drop. A
   wound-up controller fails this by taking minutes.
6. **Slew limit.** A single step from CPU 60 to CPU 200 moves the ratio by no more
   than `DEFLECT_MAX_SLEW_PER_SEC * dt`.
7. **Integral reset.** After a transition into `BASELINE`, the integral is exactly
   `0.0`.
8. **Bernoulli fidelity.** With a seeded RNG and `ratio = 0.35`, 10,000 draws split
   within ±2% of 35/65.

### 7b. The closed-loop plant simulation — the test that proves the upgrade

Model the cluster as a first-order lag, because that is what the 30s `rate()` window
plus pod startup behaves like:

```python
# capacity C = requests/sec that saturate the cluster at 100% CPU
# offered load L, deflection r  ->  load actually hitting Kubernetes = L * (1 - r)
cpu_true   = 100.0 * min(L * (1 - r) / C, 4.0)          # cap at 400%
cpu_seen  += (cpu_true - cpu_seen) * (dt / TAU)          # TAU = 15.0 s
```

Step `L` from `0.5 * C` to `2.0 * C` at t=0 and run 300 simulated seconds at
`dt = 2.0`. Assert:

- CPU settles within **±5** of the setpoint by t = 120s.
- After settling, no excursion beyond **±10** of the setpoint.
- The ratio settles at **0.625 ± 0.05**. That number is not arbitrary — holding CPU
  at 75% with `L = 2C` requires `L(1-r)/C = 0.75`, so `1 - r = 0.375` and
  `r = 0.625`. If your test passes with a materially different ratio, either the
  plant model or the controller is wrong.

### 7c. Quantify the improvement

Run the same plant twice — once with the existing binary rule, once with the PI
controller — and compute `∫|cpu - setpoint| dt` for each, plus the peak-to-trough
CPU swing after t = 60s. Assert PI is strictly better on both, and **print both
numbers in your report.** "Smoother" is a claim; these two numbers are evidence.

## 8. Acceptance in the running stack — and its honest limitation

**`cpu-sim` is open-loop.** It publishes whatever CPU percentage you set,
regardless of how much traffic the gateway deflects. Deflecting traffic does not
reduce `cpu-sim`'s output, so there is **no feedback**, and the controller will
correctly wind its way to saturation at any setting above the setpoint. That is the
controller working as designed against a plant that ignores it — not a bug, and not
a demonstration of closed-loop control either. Say so plainly rather than presenting
a saturated ratio as a success.

What Compose *can* prove — run all of it and paste the output:

```bash
docker compose up -d --build
sleep 25

# baseline: mode baseline, ratio exactly 0
curl -s localhost:8080/health; echo
curl -s localhost:8080/metrics | grep -E 'gateway_deflect_ratio|gateway_routing_mode|gateway_cpu_setpoint_percent'

# hold at 85: mode burst, ratio climbs smoothly (slew-limited), then saturates
curl -sX POST 'localhost:8002/set?pct=85'
for i in $(seq 1 24); do printf '%03ds ' $((i*5));
  curl -s localhost:8080/metrics | grep -E '^gateway_(deflect_ratio|cpu_observed_percent|deflect_integral)' | tr '\n' ' '; echo; sleep 5; done

# traffic really is split while the ratio is mid-range: hit it during the climb
for i in $(seq 1 200); do curl -s -o /dev/null localhost:8080/calculate; done
curl -s localhost:8080/metrics | grep gateway_requests_routed_total

# back to 20: ratio must return to 0 promptly (anti-windup, in the real process)
curl -sX POST 'localhost:8002/set?pct=20'
for i in $(seq 1 18); do printf '%03ds ' $((i*5));
  curl -s localhost:8080/metrics | grep -E '^gateway_(deflect_ratio|routing_mode|deflect_integral)' | tr '\n' ' '; echo; sleep 5; done

pytest tests/ -q     # every suite green, test_hysteresis.py unmodified
```

Pass criteria: ratio is exactly `0.0` in baseline; the climb honours the slew limit
(no 5s interval shows a jump larger than `DEFLECT_MAX_SLEW_PER_SEC * 5`);
`gateway_requests_routed_total` increments on **both** route labels during the climb;
after the drop to 20 the ratio reaches 0 and the integral returns to 0 within ~30s;
`pytest tests/ -q` fully green with `git diff --stat` showing `test_hysteresis.py`
untouched.

### 8b. Optional: make Compose a genuine closed loop

If you want the local stack to actually demonstrate regulation, `cpu-sim` can be
made to respond to deflection — scale its accrual by `(1 - ratio)`, either by
scraping `gateway_deflect_ratio` from the gateway's `/metrics` every tick, or via a
new `POST /couple?enabled=true` endpoint plus a `GATEWAY_METRICS_URL` env var. That
turns §7b's simulated plant into a real one you can watch in Grafana.

This is a scope addition to a file outside this task's remit. **Propose it, show the
~20 lines it would take, and wait for approval.** Do not implement it unasked.

## 9. Grafana

Add a **"Deflection Ratio"** time-series panel (0–1 axis) and overlay
`gateway_cpu_setpoint_percent` as a threshold line on the existing "CPU Observed vs
Thresholds" panel. That takes the dashboard from 6 panels to 7.

Every panel's datasource uid must remain `burstops-prometheus` — the existing six
are hardcoded to it, and a new panel without it renders "datasource not found".
Do not renumber or reorder the existing panels.

## 10. Stop and ask — do not decide these yourself

- **You want to change `update_from_cpu`, `BURST_THRESHOLD` (80.0),
  `RECOVERY_THRESHOLD` (60.0), `STALE_STATE_GRACE`, or any existing metric name.**
  This upgrade sits on top of the state machine; it does not renegotiate it.
- You want to modify `tests/test_hysteresis.py`. Never. If it fails, your change is
  wrong, not the test.
- A setpoint outside the open interval `(RECOVERY_THRESHOLD, BURST_THRESHOLD)` seems
  desirable for some reason. Explain the reason and wait.
- You want a D term, gain scheduling, or a second controller. Present the case, get
  agreement; a PI with a slew limit is the deliberate choice here.
- You want to coordinate the ratio across gateway replicas. **That is Upgrade B**
  (Redis backplane) and has its own brief. This upgrade must be correct with
  `replicas: 1` and merely *not wrong* with more.
- Editing `cpu-sim/` to close the loop (§8b), or editing
  `grafana/provisioning/dashboards/burstops.json` beyond adding one panel and one
  threshold line.
- The HMAC signing path, `FUNCTION_UPSTREAM`, `K8S_UPSTREAM`, `.env`, or
  `docker-compose.yml` would need to change. None of them should.

## 11. Report back with

1. §3's verification output, including the pre-change `pytest tests/ -q` result.
2. A **unified diff** of `gateway.py` and `gateway_entrypoint.py`, not a rewritten
   file. The diff should be small; if it is large, explain why.
3. Explicit confirmation that `update_from_cpu`'s mode logic is byte-identical, with
   the before/after of that function side by side.
4. The full new test file, and `pytest tests/ -q` output.
5. §7b's settling numbers: time to within ±5 of setpoint, the settled ratio versus
   the predicted 0.625, and the post-settling excursion range.
6. §7c's two comparison numbers — `∫|cpu - setpoint| dt` and peak-to-trough swing,
   binary versus PI — stated as a percentage improvement.
7. §8's live output, with the open-loop caveat stated in your own words.
8. The tuning you ended up with if you deviated from §4's defaults, and what you
   observed that justified it.
9. `git diff --stat` proving `tests/test_hysteresis.py`, `.env`,
   `docker-compose.yml`, `dummy-serverless/`, `azure-function/` and `k8s/` are
   unmodified.

Do not implement the Redis backplane, cost telemetry, or tracing. Those are
Upgrades B, C and D, each with its own brief.





