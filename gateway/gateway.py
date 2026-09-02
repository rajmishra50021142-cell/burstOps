"""BurstOps gateway — the spec file. READ-ONLY: do not rename constants/classes/metrics.

Every later component (dummy or real) must stay consistent with the names,
thresholds and metric names defined here. New config goes through
gateway_entrypoint.py (env-var shim), never into this file.
"""
import asyncio
import hashlib
import hmac
import logging
import random
import time
from contextlib import asynccontextmanager
from enum import Enum

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# ---------------------------------------------------------------- config ----
PROMETHEUS_URL = "http://prometheus:9090/api/v1/query"
PROM_QUERY = 'avg(rate(container_cpu_usage_seconds_total{namespace="burstops"}[30s])) * 100'
POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 1.5
BURST_THRESHOLD = 80.0
RECOVERY_THRESHOLD = 60.0
STALE_STATE_GRACE_SECONDS = 15
FAIL_OPEN_TO_BURST = True

# --- Upgrade A: PI proportional deflection ---------------------------------
# Binary deflection is bang-bang control: 100% serverless at 80% CPU collapses
# the cluster to idle, 100% back below 60% slams it again — oscillation even
# with hysteresis. Instead: hold CPU near a SETPOINT by deflecting a
# continuously-varying fraction of requests (Bernoulli per request).
#
# Setpoint MUST sit strictly inside the dead band (60, 80): below 60 fights
# the state machine (controller drives CPU down, mode exits BURST, ratio
# forces to 0, CPU spikes — reintroducing the oscillation one layer up).
CPU_SETPOINT_PERCENT = 75.0
DEFLECT_KP = 0.04              # e=5 -> 20% deflected; e=25 (CPU 100) -> saturated
DEFLECT_KI = 0.004              # KP/10; steady e=5 adds ~0.02/s, matching plant lag
MAX_DEFLECT_RATIO = 1.0         # lower to keep a floor of traffic on Kubernetes
DEFLECT_MAX_SLEW_PER_SEC = 0.10 # full 0->1 traverse in ~10s, slower than the plant
DEFLECT_INTEGRAL_CLAMP = 1.0    # integral alone can saturate, no further
# NOTE: deliberately a PI, not a PID — the measurement is avg(rate([30s]))
# smoothed; a D term would amplify scrape noise and buy nothing.

GATEWAY_INSTANCE_ID = None  # set by gateway_entrypoint; hostname+pid default in redis_backplane
K8S_UPSTREAM = "http://k8s-upstream.invalid:8000"
FUNCTION_UPSTREAM = "http://function-upstream.invalid:8001/calculate"
FUNCTION_KEY = "placeholder-function-key"
GATEWAY_HMAC_SECRET = "placeholder-hmac-secret"

# --------------------------------------------------------------- metrics ----
gateway_routing_mode = Gauge(
    "gateway_routing_mode", "0 = baseline/K8s, 1 = burst/serverless"
)
gateway_cpu_observed_percent = Gauge(
    "gateway_cpu_observed_percent", "Last CPU% seen by the poller"
)
gateway_prometheus_poll_failures_total = Counter(
    "gateway_prometheus_poll_failures_total", "Failed polls against Prometheus"
)
gateway_requests_routed_total = Counter(
    "gateway_requests_routed_total", "Requests routed by destination", ["route"]
)
gateway_upstream_latency_seconds = Histogram(
    "gateway_upstream_latency_seconds", "Upstream response latency", ["route"]
)
gateway_state_transitions_total = Counter(
    "gateway_state_transitions_total", "Every mode flip", ["direction"]
)
# Upgrade A additions (existing six names/labels byte-identical):
gateway_deflect_ratio = Gauge(
    "gateway_deflect_ratio", "Current fraction of traffic deflected, 0.0-1.0"
)
gateway_cpu_setpoint_percent = Gauge(
    "gateway_cpu_setpoint_percent", "The CPU% the PI controller targets"
)
gateway_deflect_integral = Gauge(
    "gateway_deflect_integral", "PI integral term — windup detector"
)
# Upgrade C additions (FinOps). NO gateway_cost_saved_* — the node bill is
# sunk; at the margin deflection COSTS ~1.75x more per request. What
# bursting buys is availability during the HPA lag window, quantified by
# gateway_hpa_lag_cost_usd_total.
gateway_cost_usd_total = Counter(
    "gateway_cost_usd_total",
    "List-price spend attributed per route (k8s series is an amortization, "
    "not an incremental charge)",
    ["route"],
)
gateway_burst_premium_usd_total = Counter(
    "gateway_burst_premium_usd_total",
    "(serverless - k8s) per deflected request: what bursting cost extra",
)
gateway_hpa_lag_cost_usd_total = Counter(
    "gateway_hpa_lag_cost_usd_total",
    "Premium accrued in the first HPA_LAG_WINDOW_SECONDS of each burst "
    "episode — the price of provisioning lag",
)
gateway_breakeven_overflow_rps = Gauge(
    "gateway_breakeven_overflow_rps",
    "Sustained overflow rate at which adding a node becomes cheaper",
)
gateway_cost_per_request_usd = Gauge(
    "gateway_cost_per_request_usd", "Current unit cost, per route", ["route"]
)
gateway_assumed_capacity_rps = Gauge(
    "gateway_assumed_capacity_rps",
    "Surfaces the CLUSTER_CAPACITY_RPS modelling assumption instead of hiding it",
)
# Upgrade B additions (Redis backplane):
gateway_is_leader = Gauge("gateway_is_leader", "0/1; sums to exactly 1 across replicas")
gateway_leader_elections_total = Counter("gateway_leader_elections_total", "Churn detector; steady-state should be flat")
gateway_redis_up = Gauge("gateway_redis_up", "0/1")
gateway_redis_errors_total = Counter("gateway_redis_errors_total", "Per-operation failure counts", ["op"])
gateway_shared_state_age_seconds = Gauge("gateway_shared_state_age_seconds", "How stale this replica's copy is")
gateway_prometheus_polls_total = Counter("gateway_prometheus_polls_total", "Proves polling is 1x not Nx under the backplane")

# ---------------------------------------------------------------- logging ---
logger = logging.getLogger("burstops.gateway")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(_h)


# ----------------------------------------------------------- state machine --
class Mode(str, Enum):
    BASELINE = "baseline"
    BURST = "burst"


class RoutingState:
    """Dual-threshold hysteresis state machine.

    It takes CPU >= 80 to enter BURST; CPU must drop *below* 60 — not just
    below 80 — to return to BASELINE. Between 60 and 80 is a dead band where
    the mode never changes, preventing flapping around a single threshold.
    """

    def __init__(self) -> None:
        self.mode: Mode = Mode.BASELINE
        self.cpu_observed: float = 0.0
        self.last_successful_poll: float = 0.0
        # Upgrade A: independent second layer — never folded into mode logic.
        self.deflect_ratio: float = 0.0
        self._integral: float = 0.0
        self._setpoint_validation()

    def update_from_cpu(self, cpu_percent: float) -> None:
        """Called by the poller on every successful scrape."""
        self.cpu_observed = cpu_percent
        if self.mode is Mode.BASELINE and cpu_percent >= BURST_THRESHOLD:
            self._transition(Mode.BURST)
        elif self.mode is Mode.BURST and cpu_percent < RECOVERY_THRESHOLD:
            self._transition(Mode.BASELINE)

    def apply_fail_safe(self) -> None:
        """Called on poll failure. Tolerate blips <= STALE_STATE_GRACE_SECONDS,
        then fail open to BURST rather than routing blind against an unwatched cluster."""
        if self.last_successful_poll == 0.0:
            return
        stale_for = time.time() - self.last_successful_poll
        if stale_for > STALE_STATE_GRACE_SECONDS:
            if FAIL_OPEN_TO_BURST and self.mode is not Mode.BURST:
                logger.error(
                    "Prometheus unreachable for %.1fs (> %ds grace); failing open to BURST",
                    stale_for, STALE_STATE_GRACE_SECONDS,
                )
                self._transition(Mode.BURST)

    def _transition(self, new_mode: Mode) -> None:
        old = self.mode
        self.mode = new_mode
        direction = f"{old.value}_to_{new_mode.value}"
        gateway_state_transitions_total.labels(direction=direction).inc()
        logger.info("routing state transition: %s (cpu=%.2f)", direction, self.cpu_observed)
        _record_transition_cost(new_mode)
        if new_mode is Mode.BASELINE:
            # fresh burst starts from a clean integral, not the last one's history
            self._integral = 0.0
            self.deflect_ratio = 0.0

    @staticmethod
    def _setpoint_validation() -> None:
        """The setpoint must sit strictly inside the dead band — a setpoint
        below RECOVERY_THRESHOLD makes controller and state machine fight,
        reintroducing the oscillation this upgrade exists to remove. Chosen
        behaviour: refuse loudly at startup."""
        if not (RECOVERY_THRESHOLD < CPU_SETPOINT_PERCENT < BURST_THRESHOLD):
            raise ValueError(
                f"CPU_SETPOINT_PERCENT={CPU_SETPOINT_PERCENT} must be strictly "
                f"inside ({RECOVERY_THRESHOLD}, {BURST_THRESHOLD})"
            )

    # ---- Upgrade A: the PI controller (runs once per poll cycle) --------
    def update_deflection(self, dt: float) -> None:
        """PI control law with conditional anti-windup + slew limiting.

        Invariants (tests assert): deflect_ratio == 0.0 whenever mode is
        BASELINE; 0 <= ratio <= MAX_DEFLECT_RATIO; inside BURST the ratio MAY
        be 0.0 — that is how CPU falls far enough to leave BURST.
        """
        if self.mode is Mode.BASELINE:
            self.deflect_ratio = 0.0
            return

        e = self.cpu_observed - CPU_SETPOINT_PERCENT  # >0: too hot, deflect more
        p_term = DEFLECT_KP * e
        raw = p_term + self._integral

        # conditional integration: skip when saturated in the error's direction
        saturated_high = raw >= MAX_DEFLECT_RATIO and e > 0
        saturated_low = raw <= 0.0 and e < 0
        if not (saturated_high or saturated_low):
            self._integral += DEFLECT_KI * e * dt
            self._integral = _clamp(self._integral, 0.0, DEFLECT_INTEGRAL_CLAMP)
            raw = p_term + self._integral

        target = _clamp(raw, 0.0, MAX_DEFLECT_RATIO)
        max_step = DEFLECT_MAX_SLEW_PER_SEC * dt
        self.deflect_ratio = _clamp(
            target, self.deflect_ratio - max_step, self.deflect_ratio + max_step
        )
        gateway_deflect_ratio.set(self.deflect_ratio)
        gateway_deflect_integral.set(self._integral)


routing_state = RoutingState()

# ---- Upgrade C: cost accounting state --------------------------------------
# Track burst-episode start to accrue HPA-lag cost only inside the window.
import costing  # stdlib-only pure module, same directory

_cost_state = {"burst_started": None}

# ---- Upgrade B: Redis backplane (opt-in via REDIS_URL; None => off) --------
_backplane = None  # replaced by gateway_entrypoint after constants are patched


def _apply_shared_state(bp) -> None:
    """Follower: adopt the leader's decision. Follower-side fail-open still
    fires through its own polling fallback, never here."""
    shared = bp.shared
    if shared.get("mode") == Mode.BURST.value and routing_state.mode is not Mode.BASELINE:
        routing_state.deflect_ratio = shared.get("deflect_ratio", 0.0)
    elif shared.get("mode") == Mode.BASELINE.value and routing_state.mode is Mode.BASELINE:
        routing_state.deflect_ratio = 0.0
    if shared.get("mode") == Mode.BURST.value and routing_state.mode is not Mode.BURST:
        routing_state._transition(Mode.BURST)
        routing_state.deflect_ratio = shared.get("deflect_ratio", 0.0)
    elif shared.get("mode") == Mode.BASELINE.value and routing_state.mode is Mode.BURST:
        routing_state._transition(Mode.BASELINE)


async def _poll_prometheus_once(dt: float) -> None:
    """One poll + state update + controller tick. Shared by the standalone
    loop, the leader path, and the follower fallback."""
    client = _get_client()
    try:
        gateway_prometheus_polls_total.inc()
        resp = await client.get(
            PROMETHEUS_URL, params={"query": PROM_QUERY}, timeout=POLL_TIMEOUT_SECONDS
        )
        resp.raise_for_status()
        data = resp.json()
        result = data.get("data", {}).get("result", [])
        if result:
            value = float(result[0]["value"][1])
            routing_state.update_from_cpu(value)
            routing_state.last_successful_poll = time.time()
            routing_state.update_deflection(dt)
        else:
            gateway_prometheus_poll_failures_total.inc()
            routing_state.apply_fail_safe()
    except Exception as exc:  # noqa: BLE001
        gateway_prometheus_poll_failures_total.inc()
        logger.warning("prometheus poll failed: %s", exc)
        routing_state.apply_fail_safe()


async def backplane_loop() -> None:
    """Leader: poll + run state machine + PI controller + publish. Follower:
    refresh the local cache; if shared state is stale/unreadable, poll
    Prometheus ourselves (today's single-replica behaviour). The request
    path NEVER awaits Redis — this runs entirely in the background."""
    import redis_backplane as rb

    bp = _backplane
    last = time.monotonic()
    while True:
        await asyncio.sleep(rb.REDIS_LEADER_RENEW_MS / 1000.0)
        dt = time.monotonic() - last
        last = time.monotonic()
        try:
            if bp.is_leader:
                # I hold the lease: RENEW only — never re-acquire (nx would
                # fail against my own live lease and demote me).
                renewed = await bp.renew_lease()
                if renewed:
                    await _poll_prometheus_once(dt)
                    await bp.publish_state(
                        routing_state.mode.value,
                        routing_state.deflect_ratio,
                        routing_state.cpu_observed,
                    )
                else:
                    await bp.refresh_shared_state()
                    if bp.shared_state_fresh():
                        _apply_shared_state(bp)
                    else:
                        await _poll_prometheus_once(dt)  # local fallback
            else:
                acquired = await bp.try_acquire()
                if not acquired:
                    await bp.refresh_shared_state()
                    if bp.shared_state_fresh():
                        _apply_shared_state(bp)
                    else:
                        await _poll_prometheus_once(dt)  # local fallback
                else:
                    await _poll_prometheus_once(dt)
                    await bp.publish_state(
                        routing_state.mode.value,
                        routing_state.deflect_ratio,
                        routing_state.cpu_observed,
                    )
        except Exception:  # noqa: BLE001 — degrade, never crash the pod
            logger.warning("backplane cycle degraded; falling back this cycle")


def _init_cost_gauges() -> None:
    gateway_assumed_capacity_rps.set(costing.CLUSTER_CAPACITY_RPS)
    gateway_cost_per_request_usd.labels(route="k8s").set(
        costing.kubernetes_cost_per_request()
    )
    gateway_cost_per_request_usd.labels(route="serverless").set(
        costing.serverless_cost_per_request(costing.MIN_BILLABLE_SECONDS)
    )
    gateway_breakeven_overflow_rps.set(
        costing.breakeven_overflow_rps(duration_s=costing.MIN_BILLABLE_SECONDS)
    )


def _record_transition_cost(new_mode: Mode) -> None:
    if new_mode is Mode.BURST:
        _cost_state["burst_started"] = time.time()
    else:
        _cost_state["burst_started"] = None


def _record_request_cost(route: str, elapsed_s: float) -> None:
    """Called AFTER the upstream call returns, with the observed duration —
    the real duration drives the bill, never a nominal value."""
    if route == "serverless":
        s_cost = costing.serverless_cost_per_request(elapsed_s)
        k_cost = costing.kubernetes_cost_per_request()
        gateway_cost_usd_total.labels(route="serverless").inc(s_cost)
        gateway_burst_premium_usd_total.inc(s_cost - k_cost)
        started = _cost_state["burst_started"]
        if started is not None and (time.time() - started) < costing.HPA_LAG_WINDOW_SECONDS:
            gateway_hpa_lag_cost_usd_total.inc(s_cost - k_cost)
    else:
        gateway_cost_usd_total.labels(route="k8s").inc(
            costing.kubernetes_cost_per_request()
        )


_init_cost_gauges()

# ---------------------------------------------------------------- httpx -----
_client: httpx.AsyncClient | None = None

# Upgrade A: seeded-from-OS RNG exposed so tests can substitute a seeded
# instance. Single event loop under uvicorn — no threading concern.
_rng = random.Random()


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
    return _client


# ---------------------------------------------------------------- signing ---
def sign_request(secret: str, timestamp: str, body: bytes) -> str:
    """HMAC-SHA256 over f"{timestamp}:".encode() + body. Hex digest.

    This is THE reference implementation — every downstream verifier must
    match it exactly: headers x-functions-key / x-gateway-timestamp /
    x-gateway-signature, same f"{timestamp}:" prefix convention, UTF-8
    encoded secret, SHA-256, hex digest.
    """
    return hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}:".encode("utf-8") + body,
        hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------- poller ----
async def poll_prometheus_loop() -> None:
    """Background task: query Prometheus every POLL_INTERVAL_SECONDS.

    Deliberately decoupled from the request path — a slow or failing
    Prometheus must never block a live request. Upgrade A: the PI controller
    runs once per cycle here, using measured elapsed time (never nominal).
    Upgrade B: if the backplane is active, this loop is NOT started —
    backplane_loop() replaces it (leader polls 1x, followers read state).
    """
    last = time.monotonic()
    while True:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        dt = time.monotonic() - last
        last = time.monotonic()
        await _poll_prometheus_once(dt)


# ----------------------------------------------------------------- app ------
@asynccontextmanager
async def lifespan(app: FastAPI):
    if _backplane is not None:
        task = asyncio.create_task(backplane_loop())
        logger.info("gateway up; redis backplane active (instance=%s)", GATEWAY_INSTANCE_ID)
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            try:
                await _backplane.release_lease()
            except Exception:  # noqa: BLE001
                pass
    else:
        task = asyncio.create_task(poll_prometheus_loop())
        logger.info("gateway up; poller started (interval=%ss)", POLL_INTERVAL_SECONDS)
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="BurstOps Gateway", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"mode": routing_state.mode.value, "last_cpu": routing_state.cpu_observed}


@app.api_route("/calculate", methods=["GET", "POST"])
async def calculate(request: Request):
    # Upgrade A: stochastic (Bernoulli) selection — one draw, one compare.
    # Stateless, needs no coordination, stays correct across N replicas.
    if routing_state.mode is Mode.BURST and _rng.random() < routing_state.deflect_ratio:
        route = "serverless"
    else:
        route = "k8s"
    if route == "serverless":
        upstream = FUNCTION_UPSTREAM  # full URL including /calculate
    else:
        # K8S_UPSTREAM is a base URL (host:port); the calculate path is ours.
        upstream = f"{K8S_UPSTREAM.rstrip('/')}/calculate"
    body = await request.body()

    headers = {}
    if route == "serverless":
        timestamp = str(int(time.time()))
        signature = sign_request(GATEWAY_HMAC_SECRET, timestamp, body)
        headers = {
            "x-functions-key": FUNCTION_KEY,
            "x-gateway-timestamp": timestamp,
            "x-gateway-signature": signature,
        }

    client = _get_client()
    start = time.perf_counter()
    try:
        resp = await client.request(
            request.method,
            upstream,
            content=body,
            headers=headers,
            params=request.query_params,
        )
        elapsed = time.perf_counter() - start
        gateway_upstream_latency_seconds.labels(route=route).observe(elapsed)
        gateway_requests_routed_total.labels(route=route).inc()
        _record_request_cost(route, elapsed)
        return PlainTextResponse(
            content=resp.text,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type", "application/json"),
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - start
        gateway_upstream_latency_seconds.labels(route=route).observe(elapsed)
        gateway_requests_routed_total.labels(route=route).inc()
        logger.error("upstream %s unavailable: %s", route, exc)
        return JSONResponse({"detail": "upstream unavailable"}, status_code=502)


@app.get("/metrics")
async def metrics():
    gateway_routing_mode.set(1 if routing_state.mode is Mode.BURST else 0)
    gateway_cpu_observed_percent.set(routing_state.cpu_observed)
    gateway_cpu_setpoint_percent.set(CPU_SETPOINT_PERCENT)
    gateway_deflect_ratio.set(routing_state.deflect_ratio)
    gateway_deflect_integral.set(routing_state._integral)
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
