"""Golden Trio Controller & Capacity Model for BurstOps Gateway.

Attached cleanly from gateway_entrypoint.py without modifying gateway.py.
Implements:
1. Novelty 1: Self-Tuning AIMD Burst Threshold theta(t) via SLO Tail-Latency Feedback
2. Novelty 2: Derivative-Based (dU/dt) Predictive Serverless Pre-Warming
3. Novelty 3: Semantic Compute-to-Communication Ratio (gamma) Asymmetric Routing
4. Base Server Capacity Tracking (10 slots = 100% saturation / 500m vCPU)
"""
import asyncio
import collections
import json
import logging
import math
import os
import random
import time
from typing import Any, Callable, Dict, Optional, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import Counter, Gauge

logger = logging.getLogger("burstops.golden_trio")

# --- Configuration Constants ---
MAX_BASE_COMPUTE_SLOTS = int(os.environ.get("MAX_BASE_COMPUTE_SLOTS", "10"))
SLO_TARGET_P95_MS = float(os.environ.get("SLO_TARGET_P95_MS", "650.0"))
AIMD_MIN_THRESHOLD = 0.60
AIMD_MAX_THRESHOLD = 0.92
PREWARM_COOLDOWN_SECONDS = 30.0
PREWARM_VELOCITY_TRIGGER = 5.0        # %/s
PREWARM_TIME_TO_BREACH_TRIGGER = 4.0  # seconds
GAMMA_THRESHOLD = 1.5
SERVERLESS_ROUNDTRIP_OVERHEAD_MS = 60.0

# --- Prometheus Metrics ---
burstops_dynamic_threshold_ratio = Gauge(
    "burstops_dynamic_threshold_ratio", "Dynamic AIMD burst threshold ratio, 0.60 to 0.92"
)
burstops_aks_p95_latency_ms = Gauge(
    "burstops_aks_p95_latency_ms", "Rolling p95 latency of AKS base cluster in ms"
)
burstops_composite_utilization_percent = Gauge(
    "burstops_composite_utilization_percent", "Composite utilization max(slots/10, cpu)"
)
burstops_active_compute_slots = Gauge(
    "burstops_active_compute_slots", "Active concurrent Digital Twin compute slots on AKS"
)
burstops_prewarm_pings_total = Counter(
    "burstops_prewarm_pings_total", "Speculative pre-warm pings sent to Azure Function"
)
burstops_load_velocity_percent_per_sec = Gauge(
    "burstops_load_velocity_percent_per_sec", "Derivative dU/dt load velocity in % per second"
)
burstops_gamma_requests_total = Counter(
    "burstops_gamma_requests_total", "Requests routed by semantic gamma class", ["classification", "route"]
)

# Rolling State
_aks_latency_window: collections.deque = collections.deque(maxlen=30)
_utilization_history: collections.deque = collections.deque(maxlen=10)
_last_slo_violation_time: float = 0.0
_last_prewarm_ping_time: float = 0.0
_prewarm_state: str = "IDLE"
_prewarm_saves_count: int = 0
_in_memory_slots: int = 0
class AIMDThresholdController:
    """Novelty 1: Self-tuning AIMD threshold controller."""

    def __init__(
        self,
        target_p95_ms: float = SLO_TARGET_P95_MS,
        initial_theta: float = 0.80,
        min_theta: float = AIMD_MIN_THRESHOLD,
        max_theta: float = AIMD_MAX_THRESHOLD,
    ):
        self.target_p95_ms = target_p95_ms
        self.current_theta = initial_theta
        self.min_theta = min_theta
        self.max_theta = max_theta
        self.last_slo_violation_time = 0.0
        self.last_direction = "STEADY"

    def update(self, latency_samples, now: Optional[float] = None) -> float:
        if now is None:
            now = time.time()
        if not latency_samples:
            return self.current_theta
        sorted_l = sorted(latency_samples)
        idx = max(0, min(len(sorted_l) - 1, int(math.ceil(0.95 * len(sorted_l))) - 1))
        p95 = sorted_l[idx]
        if p95 > self.target_p95_ms:
            self.current_theta = max(self.min_theta, self.current_theta * 0.92)
            self.last_slo_violation_time = now
            self.last_direction = "DECREASE"
        elif p95 < 0.65 * self.target_p95_ms and (now - self.last_slo_violation_time) > 15.0:
            self.current_theta = min(self.max_theta, self.current_theta + 0.01)
            self.last_direction = "INCREASE"
        return self.current_theta


class PredictivePrewarmer:
    """Novelty 2: Derivative-based predictive pre-warming controller."""

    def __init__(
        self,
        velocity_trigger_pct_per_s: float = PREWARM_VELOCITY_TRIGGER,
        time_to_breach_trigger_s: float = PREWARM_TIME_TO_BREACH_TRIGGER,
        cooldown_s: float = PREWARM_COOLDOWN_SECONDS,
    ):
        self.velocity_trigger = velocity_trigger_pct_per_s
        self.breach_trigger = time_to_breach_trigger_s
        self.cooldown_s = cooldown_s
        self.history = collections.deque(maxlen=10)
        self.last_prewarm_time = 0.0
        self.state = "IDLE"
        self.prewarm_saves_count = 0

    def update_load_velocity(
        self, current_u: float, now: float, current_theta: float = 0.80
    ) -> Tuple[float, Optional[float]]:
        self.history.append((now, current_u))
        if len(self.history) < 2:
            return 0.0, None
        t_old, u_old = self.history[0]
        dt = now - t_old
        if dt < 0.4:
            return 0.0, None
        velocity = (current_u - u_old) / dt
        thresh = current_theta * 100.0
        t_breach = (thresh - current_u) / velocity if velocity > 0 else None
        return round(velocity, 2), round(t_breach, 2) if t_breach is not None else None

    def should_trigger_prewarm(
        self,
        current_u: float,
        current_theta: float,
        velocity_pct_per_s: float,
        t_breach_s: Optional[float],
        now: float,
    ) -> bool:
        thresh = current_theta * 100.0
        if current_u >= thresh:
            return False
        if (now - self.last_prewarm_time) < self.cooldown_s:
            return False
        if (
            velocity_pct_per_s >= self.velocity_trigger
            and t_breach_s is not None
            and 0 < t_breach_s <= self.breach_trigger
        ):
            return True
        return False


def get_routing_decision_for_gamma(
    gamma: float, composite_utilization: float, base_deflect_ratio: float
) -> Tuple[str, str]:
    """Novelty 3: Routing decision using gamma ratio."""
    if gamma < GAMMA_THRESHOLD:
        if composite_utilization < 98.0:
            return "k8s", "PINNED_AKS_LOW_GAMMA"
        return "serverless", "DEFLECTED_EMERGENCY_CAPACITY"
    else:
        if base_deflect_ratio >= 0.5:
            return "serverless", "DEFLECTED_SERVERLESS_HIGH_GAMMA"
        return "k8s", "BASELINE_K8S_HIGH_GAMMA"


def calculate_semantic_gamma(payload: Dict[str, Any]) -> Tuple[float, float]:
    """Novelty 3: Estimates compute cost and calculates gamma = C_est / N_overhead."""
    subsystem = payload.get("subsystem", "").upper()
    iterations = int(payload.get("monte_carlo_iterations", 200_000))

    if subsystem == "MONTE_CARLO_RUL":
        c_est = 550.0 * (iterations / 200_000.0)
    elif subsystem == "ROTOR_FFT_HARMONICS":
        c_est = 380.0
    elif subsystem == "THERMAL_STATE_CHECK":
        c_est = 25.0
    else:
        c_est = 100.0  # Legacy / default

    gamma = round(c_est / SERVERLESS_ROUNDTRIP_OVERHEAD_MS, 2)
    return gamma, c_est


def record_aks_latency_sample(gw_mod, latency_ms: float, now: float) -> None:
    """Novelty 1: Updates rolling p95 latency and applies AIMD feedback."""
    global _last_slo_violation_time
    _aks_latency_window.append(latency_ms)
    if len(_aks_latency_window) >= 5:
        sorted_l = sorted(_aks_latency_window)
        idx = max(0, min(len(sorted_l) - 1, int(math.ceil(0.95 * len(sorted_l))) - 1))
        p95 = sorted_l[idx]
        gw_mod.routing_state.aks_p95_latency_ms = p95
        burstops_aks_p95_latency_ms.set(p95)

        # Multiplicative Decrease (Early Protection)
        if p95 > SLO_TARGET_P95_MS:
            gw_mod.routing_state.dynamic_threshold = max(
                AIMD_MIN_THRESHOLD, gw_mod.routing_state.dynamic_threshold * 0.92
            )
            _last_slo_violation_time = now
        # Additive Increase (FinOps Optimization)
        elif p95 < 0.65 * SLO_TARGET_P95_MS and (now - _last_slo_violation_time) > 15.0:
            gw_mod.routing_state.dynamic_threshold = min(
                AIMD_MAX_THRESHOLD, gw_mod.routing_state.dynamic_threshold + 0.01
            )
        burstops_dynamic_threshold_ratio.set(gw_mod.routing_state.dynamic_threshold)


def update_load_velocity(gw_mod, current_u: float, now: float) -> Tuple[float, float]:
    """Novelty 2: Computes derivative load velocity dU/dt and estimated time to breach."""
    _utilization_history.append((now, current_u))
    if len(_utilization_history) < 2:
        return 0.0, 999.0
    t_old, u_old = _utilization_history[0]
    dt = now - t_old
    if dt < 0.4:
        return gw_mod.routing_state.load_velocity, 999.0
    velocity = (current_u - u_old) / dt
    gw_mod.routing_state.load_velocity = round(velocity, 2)
    burstops_load_velocity_percent_per_sec.set(gw_mod.routing_state.load_velocity)

    thresh = gw_mod.routing_state.dynamic_threshold * 100.0
    t_breach = (thresh - current_u) / max(0.001, velocity) if velocity > 0 else 999.0
    return gw_mod.routing_state.load_velocity, t_breach


async def send_speculative_prewarm(gw_mod) -> None:
    """Novelty 2: Sends an authenticated speculative pre-warm ping to Azure Function."""
    global _last_prewarm_ping_time, _prewarm_state, _prewarm_saves_count
    now = time.time()
    if (now - _last_prewarm_ping_time) < PREWARM_COOLDOWN_SECONDS:
        return
    _last_prewarm_ping_time = now
    _prewarm_state = "PREWARMING_IN_FLIGHT"
    gw_mod.routing_state.prewarm_state = _prewarm_state

    client = gw_mod._get_client()
    timestamp = str(int(time.time()))
    sig = gw_mod.sign_request(gw_mod.GATEWAY_HMAC_SECRET, timestamp, b"")
    headers = {
        "x-functions-key": gw_mod.FUNCTION_KEY,
        "x-gateway-timestamp": timestamp,
        "x-gateway-signature": sig,
        "x-burstops-prewarm": "true",
    }
    try:
        resp = await client.post(gw_mod.FUNCTION_UPSTREAM, headers=headers, timeout=3.5)
        if resp.status_code == 200:
            _prewarm_state = "WARM_READY"
            gw_mod.routing_state.prewarm_state = _prewarm_state
            burstops_prewarm_pings_total.inc()
            _prewarm_saves_count += 1
            logger.info("predictive pre-warm succeeded (Azure Function warm and ready)")
    except Exception as exc:
        logger.debug("prewarm ping notice: %s", exc)


async def get_active_slots(gw_mod) -> int:
    if gw_mod._backplane is not None and hasattr(gw_mod._backplane, "get_active_slots"):
        return await gw_mod._backplane.get_active_slots()
    return _in_memory_slots


async def incr_slot(gw_mod) -> int:
    global _in_memory_slots
    if gw_mod._backplane is not None and hasattr(gw_mod._backplane, "incr_active_slots"):
        return await gw_mod._backplane.incr_active_slots()
    async with _slots_lock:
        _in_memory_slots += 1
        return _in_memory_slots


async def decr_slot(gw_mod) -> int:
    global _in_memory_slots
    if gw_mod._backplane is not None and hasattr(gw_mod._backplane, "decr_active_slots"):
        return await gw_mod._backplane.decr_active_slots()
    async with _slots_lock:
        _in_memory_slots = max(0, _in_memory_slots - 1)
        return _in_memory_slots


def install_golden_trio(gw_mod):
    """Installs the Golden Trio novel controllers into the gateway app and poller."""
    logger.info("Installing Golden Trio novel controllers and capacity tracking...")

    # Initialize RoutingState extensions
    rs = gw_mod.routing_state
    rs.dynamic_threshold = 0.80
    rs.aks_p95_latency_ms = 0.0
    rs.active_compute_slots = 0
    rs.composite_utilization = 0.0
    rs.load_velocity = 0.0
    rs.prewarm_state = "IDLE"

    burstops_dynamic_threshold_ratio.set(0.80)
    burstops_composite_utilization_percent.set(0.0)
    burstops_active_compute_slots.set(0)

    # Wrap _poll_prometheus_once to integrate velocity, composite util, and pre-warm triggers
    orig_poll = gw_mod._poll_prometheus_once

    async def wrapped_poll(dt: float):
        await orig_poll(dt)
        now = time.time()
        slots = await get_active_slots(gw_mod)
        rs.active_compute_slots = slots
        burstops_active_compute_slots.set(slots)

        slot_util = (slots / max(1, MAX_BASE_COMPUTE_SLOTS)) * 100.0
        rs.composite_utilization = max(rs.cpu_observed, slot_util)
        burstops_composite_utilization_percent.set(rs.composite_utilization)

        vel, t_breach = update_load_velocity(gw_mod, rs.composite_utilization, now)

        # Novelty 2: Pre-Warm Trigger Check
        if (
            rs.mode is gw_mod.Mode.BASELINE
            and vel >= PREWARM_VELOCITY_TRIGGER
            and 0 < t_breach <= PREWARM_TIME_TO_BREACH_TRIGGER
        ):
            asyncio.create_task(send_speculative_prewarm(gw_mod))

        # Check dynamic threshold for mode entry
        eff_thresh = rs.dynamic_threshold * 100.0
        if rs.mode is gw_mod.Mode.BASELINE and rs.composite_utilization >= eff_thresh:
            rs._transition(gw_mod.Mode.BURST)
        elif rs.mode is gw_mod.Mode.BURST and rs.composite_utilization < gw_mod.RECOVERY_THRESHOLD:
            rs._transition(gw_mod.Mode.BASELINE)

    gw_mod._poll_prometheus_once = wrapped_poll

    # Add Golden Trio status endpoint
    @gw_mod.app.get("/api/golden-trio/status")
    async def golden_trio_status():
        slots = await get_active_slots(gw_mod)
        return {
            "capacity_model": {
                "aks_base_capacity_slots": MAX_BASE_COMPUTE_SLOTS,
                "active_compute_slots": slots,
                "slot_saturation_pct": round((slots / max(1, MAX_BASE_COMPUTE_SLOTS)) * 100.0, 1),
                "cpu_limit": "500m (0.5 vCPU)",
                "memory_limit": "512Mi",
                "composite_utilization_pct": round(rs.composite_utilization, 1),
                "explanation": "100% capacity = 10 concurrent heavy Digital Twin computations (or 500m vCPU). 80% threshold = 8 active compute slots (or 400m vCPU).",
            },
            "novelty_1_aimd_threshold": {
                "current_threshold_theta": round(rs.dynamic_threshold, 4),
                "current_threshold_pct": round(rs.dynamic_threshold * 100.0, 1),
                "aks_p95_latency_ms": round(rs.aks_p95_latency_ms, 1),
                "slo_target_p95_ms": SLO_TARGET_P95_MS,
                "bounds": [AIMD_MIN_THRESHOLD, AIMD_MAX_THRESHOLD],
                "mode": rs.mode.value,
            },
            "novelty_2_predictive_prewarm": {
                "load_velocity_pct_per_s": rs.load_velocity,
                "prewarm_state": _prewarm_state,
                "prewarm_saves_count": _prewarm_saves_count,
                "velocity_trigger_pct_per_s": PREWARM_VELOCITY_TRIGGER,
                "time_to_breach_trigger_s": PREWARM_TIME_TO_BREACH_TRIGGER,
            },
            "novelty_3_semantic_gamma": {
                "gamma_threshold": GAMMA_THRESHOLD,
                "subsystems": {
                    "MONTE_CARLO_RUL": {"gamma": 9.17, "policy": "Deflect to Azure Serverless"},
                    "ROTOR_FFT_HARMONICS": {"gamma": 6.33, "policy": "Deflect to Azure Serverless"},
                    "THERMAL_STATE_CHECK": {"gamma": 0.42, "policy": "Pinned to AKS Base Server"},
                },
            },
        }

    # Core Dispatcher supporting both /calculate and /api/twin/compute
    async def handle_compute_request(request: Request):
        body = await request.body()
        now = time.time()

        body_json: Dict[str, Any] = {}
        if body:
            try:
                body_json = json.loads(body.decode("utf-8"))
            except Exception:
                body_json = {}

        for k, v in request.query_params.items():
            if k not in body_json:
                body_json[k] = v

        gamma, c_est = calculate_semantic_gamma(body_json)

        slots = await get_active_slots(gw_mod)
        rs.active_compute_slots = slots
        slot_util = (slots / max(1, MAX_BASE_COMPUTE_SLOTS)) * 100.0
        rs.composite_utilization = max(rs.cpu_observed, slot_util)

        vel, t_breach = update_load_velocity(gw_mod, rs.composite_utilization, now)
        if (
            rs.mode is gw_mod.Mode.BASELINE
            and vel >= PREWARM_VELOCITY_TRIGGER
            and 0 < t_breach <= PREWARM_TIME_TO_BREACH_TRIGGER
        ):
            asyncio.create_task(send_speculative_prewarm(gw_mod))

        eff_thresh = rs.dynamic_threshold * 100.0
        if rs.mode is gw_mod.Mode.BASELINE and rs.composite_utilization >= eff_thresh:
            rs._transition(gw_mod.Mode.BURST)
        elif rs.mode is gw_mod.Mode.BURST and rs.composite_utilization < gw_mod.RECOVERY_THRESHOLD:
            rs._transition(gw_mod.Mode.BASELINE)

        # Novelty 3: Semantic Asymmetric Routing Policy
        if rs.mode is gw_mod.Mode.BURST:
            if gamma < GAMMA_THRESHOLD:
                if rs.composite_utilization < 98.0:
                    route = "k8s"
                    routing_reason = "PINNED_AKS_LOW_GAMMA"
                    burstops_gamma_requests_total.labels(classification="low_gamma", route="k8s").inc()
                else:
                    route = "serverless"
                    routing_reason = "EMERGENCY_SERVERLESS_SATURATED"
                    burstops_gamma_requests_total.labels(classification="low_gamma", route="serverless").inc()
            else:
                boosted_ratio = min(1.0, rs.deflect_ratio * 1.35)
                if gw_mod._rng.random() < boosted_ratio:
                    route = "serverless"
                    routing_reason = "DEFLECTED_SERVERLESS_HIGH_GAMMA"
                    burstops_gamma_requests_total.labels(classification="high_gamma", route="serverless").inc()
                else:
                    route = "k8s"
                    routing_reason = "BASELINE_K8S_BERNOULLI"
                    burstops_gamma_requests_total.labels(classification="high_gamma", route="k8s").inc()
        else:
            route = "k8s"
            routing_reason = "BASELINE_K8S_NORMAL"
            burstops_gamma_requests_total.labels(
                classification="low_gamma" if gamma < GAMMA_THRESHOLD else "high_gamma", route="k8s"
            ).inc()

        if route == "serverless":
            upstream = gw_mod.FUNCTION_UPSTREAM
        else:
            upstream = f"{gw_mod.K8S_UPSTREAM.rstrip('/')}/calculate"

        headers = {}
        if route == "serverless":
            timestamp = str(int(time.time()))
            signature = gw_mod.sign_request(gw_mod.GATEWAY_HMAC_SECRET, timestamp, body)
            headers = {
                "x-functions-key": gw_mod.FUNCTION_KEY,
                "x-gateway-timestamp": timestamp,
                "x-gateway-signature": signature,
            }

        client = gw_mod._get_client()
        start = time.perf_counter()

        slot_acquired = False
        if route == "k8s":
            await incr_slot(gw_mod)
            slot_acquired = True

        try:
            resp = await client.request(
                request.method,
                upstream,
                content=body,
                headers=headers,
                params=request.query_params,
            )
            elapsed = time.perf_counter() - start
            gw_mod.gateway_upstream_latency_seconds.labels(route=route).observe(elapsed)
            gw_mod.gateway_requests_routed_total.labels(route=route).inc()
            gw_mod._record_request_cost(route, elapsed)

            if route == "k8s":
                record_aks_latency_sample(gw_mod, elapsed * 1000.0, time.time())

            content_type = resp.headers.get("content-type", "application/json")
            response_text = resp.text

            try:
                resp_data = json.loads(response_text)
                resp_data["gateway_metadata"] = {
                    "route": route,
                    "routing_reason": routing_reason,
                    "gamma_ratio": gamma,
                    "dynamic_threshold_pct": round(rs.dynamic_threshold * 100.0, 1),
                    "load_velocity_pct_per_s": rs.load_velocity,
                    "composite_utilization_pct": round(rs.composite_utilization, 1),
                    "active_compute_slots": await get_active_slots(gw_mod),
                    "max_base_compute_slots": MAX_BASE_COMPUTE_SLOTS,
                    "prewarm_state": _prewarm_state,
                    "aks_p95_latency_ms": round(rs.aks_p95_latency_ms, 1),
                }
                resp_data["route"] = route
                resp_data["routing_reason"] = routing_reason
                resp_data["gamma_ratio"] = gamma
                response_text = json.dumps(resp_data)
            except Exception:
                pass

            extra_headers = {
                "X-BurstOps-Route": route,
                "X-BurstOps-Routing-Reason": routing_reason,
                "X-BurstOps-Gamma": f"{gamma:.2f}",
                "X-BurstOps-Dynamic-Threshold": f"{rs.dynamic_threshold * 100:.1f}",
                "X-BurstOps-Load-Velocity": f"{rs.load_velocity:.1f}",
                "X-BurstOps-Composite-Util": f"{rs.composite_utilization:.1f}",
                "X-BurstOps-Active-Slots": str(await get_active_slots(gw_mod)),
                "X-BurstOps-Prewarm-State": _prewarm_state,
            }

            return PlainTextResponse(
                content=response_text,
                status_code=resp.status_code,
                media_type=content_type,
                headers=extra_headers,
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - start
            gw_mod.gateway_upstream_latency_seconds.labels(route=route).observe(elapsed)
            gw_mod.gateway_requests_routed_total.labels(route=route).inc()
            logger.error("upstream %s unavailable: %s", route, exc)
            return JSONResponse({"detail": "upstream unavailable"}, status_code=502)
        finally:
            if slot_acquired:
                await decr_slot(gw_mod)

    # Register routes
    gw_mod.app.api_route("/api/twin/compute", methods=["GET", "POST"])(handle_compute_request)

    # Replace /calculate endpoint on app router
    for route in gw_mod.app.router.routes:
        if getattr(route, "path", None) == "/calculate":
            route.endpoint = handle_compute_request
            break

    logger.info("Golden Trio controllers installed successfully.")
