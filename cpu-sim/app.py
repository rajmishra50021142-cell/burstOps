"""cpu-sim — synthetic cAdvisor replacement for Docker Desktop.

Docker Desktop's cAdvisor runs in restricted mode and only publishes
aggregate /, /docker and /restricted metrics — never the per-container
{namespace="burstops"} series the gateway's PromQL needs. This service
publishes container_cpu_usage_seconds_total in exactly that shape, with
control endpoints to ramp the simulated load up and down.

Metric math (the contract): the gateway runs
    avg(rate(container_cpu_usage_seconds_total{namespace="burstops"}[30s])) * 100
Every series must accrue (target_pct / 100) core-seconds per wall-clock
second; since avg ignores series count, all REPLICAS series accrue at the
same full rate. Counter only ever inc()s — a lower target means a slower
rate of increase, never a decrease.
"""
import asyncio
import os
import time

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, generate_latest

INITIAL_CPU_PCT = float(os.environ.get("INITIAL_CPU_PCT", "20.0"))
TICK_SECONDS = float(os.environ.get("TICK_SECONDS", "0.5"))
RAMP_SECONDS = float(os.environ.get("RAMP_SECONDS", "5.0"))
RAMP_UP_TARGET_PCT = float(os.environ.get("RAMP_UP_TARGET_PCT", "95.0"))
RAMP_DOWN_TARGET_PCT = float(os.environ.get("RAMP_DOWN_TARGET_PCT", "20.0"))
REPLICAS = int(os.environ.get("REPLICAS", "2"))
NAMESPACE_LABEL = os.environ.get("NAMESPACE_LABEL", "burstops")
PORT = int(os.environ.get("PORT", "8002"))

# prometheus_client appends _total to counters and would double the suffix if
# we declared "container_cpu_usage_seconds_total". Declaring the bare name
# exposes exactly container_cpu_usage_seconds_total.
registry = CollectorRegistry()
cpu_usage = Counter(
    "container_cpu_usage_seconds",
    "Cumulative CPU usage in core-seconds (simulated cAdvisor shape)",
    labelnames=["namespace", "name"],
    registry=registry,
)

# Docker's container names that prometheus.yml's relabel rules stamp
# namespace="burstops" onto; mirror them so the data looks like cAdvisor's.
CONTAINER_NAMES = [f"burstops-backend-{i}" for i in range(1, REPLICAS + 1)]

app = FastAPI(title="burstops cpu-sim")

_target_pct = INITIAL_CPU_PCT
_current_pct = INITIAL_CPU_PCT
_started_at = time.time()


async def accrual_loop():
    """Glide current_pct toward target_pct at a bounded rate, then accrue.

    Uses measured dt rather than the nominal TICK_SECONDS: under load the
    loop drifts, and accruing nominal 0.5s while 0.9s passed makes rate()
    under-report and the burst threshold unreachable.
    """
    global _current_pct
    last = time.monotonic()
    while True:
        await asyncio.sleep(TICK_SECONDS)
        now = time.monotonic()
        dt = now - last
        last = now

        if RAMP_SECONDS > 0:
            step = (abs(_target_pct - _current_pct) / RAMP_SECONDS) * dt
        else:
            step = abs(_target_pct - _current_pct)
        if _current_pct < _target_pct:
            _current_pct = min(_target_pct, _current_pct + step)
        else:
            _current_pct = max(_target_pct, _current_pct - step)

        core_seconds = (_current_pct / 100.0) * dt
        for name in CONTAINER_NAMES:
            cpu_usage.labels(namespace=NAMESPACE_LABEL, name=name).inc(core_seconds)


@app.on_event("startup")
async def start_loop():
    asyncio.get_event_loop().create_task(accrual_loop())


@app.get("/metrics")
async def metrics():
    return PlainTextResponse(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ramp-up")
async def ramp_up(target: float | None = Query(default=None), seconds: float | None = Query(default=None)):
    global _target_pct, RAMP_SECONDS
    if target is not None:
        _target_pct = target
    else:
        _target_pct = RAMP_UP_TARGET_PCT
    if seconds is not None:
        RAMP_SECONDS = seconds
    return {"target_pct": _target_pct, "current_pct": _current_pct}


@app.post("/ramp-down")
async def ramp_down(target: float | None = Query(default=None), seconds: float | None = Query(default=None)):
    global _target_pct, RAMP_SECONDS
    if target is not None:
        _target_pct = target
    else:
        _target_pct = RAMP_DOWN_TARGET_PCT
    if seconds is not None:
        RAMP_SECONDS = seconds
    return {"target_pct": _target_pct, "current_pct": _current_pct}


@app.post("/set")
async def set_pct(pct: float = Query(...)):
    """Arbitrary target, clamped to 0..400 — multi-core saturation (e.g. 250
    = 2.5 cores) is a legitimate scenario and the gateway's threshold logic
    should handle it."""
    global _target_pct
    _target_pct = min(max(pct, 0.0), 400.0)
    return {"target_pct": _target_pct, "current_pct": _current_pct}


@app.get("/state")
async def state():
    cumulative = {
        name: registry.get_sample_value(
            "container_cpu_usage_seconds_total",
            {"namespace": NAMESPACE_LABEL, "name": name},
        )
        or 0.0
        for name in CONTAINER_NAMES
    }
    return JSONResponse(
        {
            "target_pct": _target_pct,
            "current_pct": _current_pct,
            "replicas": REPLICAS,
            "ramp_seconds": RAMP_SECONDS,
            "cumulative_core_seconds": cumulative,
            "uptime_s": round(time.time() - _started_at, 1),
        }
    )
