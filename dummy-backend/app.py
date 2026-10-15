"""dummy-backend — stands in for an AKS pod.

Generates genuine, non-trivial CPU work (Digital Twin physics engine / prime sieve / burn loop)
so cAdvisor and Prometheus measure realistic utilization.
"""
import asyncio
import os
import socket
import time
from typing import Any, Dict

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from digital_twin import execute_digital_twin_workload

app = FastAPI(title="burstops dummy-backend")

MAX_BASE_COMPUTE_SLOTS = int(os.environ.get("MAX_BASE_COMPUTE_SLOTS", "10"))
_active_slots = 0
_lock = asyncio.Lock()


def prime_sieve(limit: int) -> list[int]:
    """Sieve of Eratosthenes over 2..limit. 2..1000 yields 168 primes summing to 76127."""
    is_prime = bytearray([1]) * (limit + 1)
    is_prime[0] = is_prime[1] = 0
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i * i :: i] = bytearray(len(is_prime[i * i :: i]))
    return [i for i in range(2, limit + 1) if is_prime[i]]


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "hostname": socket.gethostname(),
        "active_compute_slots": _active_slots,
        "max_base_compute_slots": MAX_BASE_COMPUTE_SLOTS,
        "slot_utilization_pct": round((_active_slots / max(1, MAX_BASE_COMPUTE_SLOTS)) * 100.0, 1),
    }


@app.api_route("/calculate", methods=["GET", "POST"])
@app.api_route("/api/twin/compute", methods=["GET", "POST"])
async def calculate(request: Request):
    global _active_slots
    start_perf = time.perf_counter()
    start_proc = time.process_time()

    body_json: Dict[str, Any] = {}
    if request.method == "POST":
        try:
            body_json = await request.json()
        except Exception:
            body_json = {}

    # Extract query params as fallback
    query_params = dict(request.query_params)
    for k, v in query_params.items():
        if k not in body_json:
            body_json[k] = v

    async with _lock:
        _active_slots += 1

    try:
        # Run in thread pool to avoid blocking the async event loop during CPU work
        if "subsystem" in body_json or "twin_id" in body_json:
            result = await asyncio.to_thread(
                execute_digital_twin_workload, body_json, "AKS_BASE_POD"
            )
        else:
            # Legacy default: prime sieve (2..1000)
            primes = await asyncio.to_thread(prime_sieve, 1000)
            wall_time = round((time.perf_counter() - start_perf) * 1000.0, 2)
            cpu_time = round((time.process_time() - start_proc) * 1000.0, 2)
            result = {
                "source": "k8s",
                "impl": "dummy-backend",
                "executed_by": "AKS_BASE_POD",
                "node_hostname": socket.gethostname(),
                "hostname": socket.gethostname(),
                "process_pid": os.getpid(),
                "prime_count": len(primes),
                "prime_sum": sum(primes),
                "wall_time_ms": wall_time,
                "cpu_time_ms": cpu_time,
            }

        # Attach capacity slot telemetry
        result["active_compute_slots"] = _active_slots
        result["max_base_compute_slots"] = MAX_BASE_COMPUTE_SLOTS
        return JSONResponse(result)
    finally:
        async with _lock:
            _active_slots = max(0, _active_slots - 1)


@app.post("/burn-cpu")
async def burn_cpu(ms: int = Query(default=500, ge=1, le=30000)):
    """Busy-loop doing floating-point arithmetic for exactly `ms` milliseconds."""
    deadline = time.perf_counter() + ms / 1000.0
    x = 1.0000001
    while time.perf_counter() < deadline:
        for _ in range(1000):
            x = x * 1.0000001 + 0.0000001
    return {"status": "burned", "ms": ms, "x": x}
