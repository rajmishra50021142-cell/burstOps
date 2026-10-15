"""dummy-serverless — local stand-in for an Azure Function.

Validates x-functions-key / x-gateway-timestamp / x-gateway-signature exactly
as gateway.py generates them, supports speculative pre-warming (Novelty 2),
and executes Digital Twin physics computations or the reference prime-sieve.
"""
import asyncio
import json
import logging
import os
import random
import socket

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from digital_twin import execute_digital_twin_workload
from hmac_util import DEFAULT_MAX_CLOCK_SKEW_SECONDS, SignatureError, verify_request

logger = logging.getLogger("burstops.dummy_serverless")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(_h)

GATEWAY_HMAC_SECRET = os.environ.get("GATEWAY_HMAC_SECRET", "local-dev-secret-change-in-prod")
FUNCTION_KEY = os.environ.get("FUNCTION_KEY", "local-dev-function-key")
MAX_CLOCK_SKEW = int(os.environ.get("MAX_CLOCK_SKEW_SECONDS", str(DEFAULT_MAX_CLOCK_SKEW_SECONDS)))
MIN_LATENCY_MS = float(os.environ.get("MIN_LATENCY_MS", "50"))
MAX_LATENCY_MS = float(os.environ.get("MAX_LATENCY_MS", "150"))
PRIME_LIMIT = int(os.environ.get("PRIME_LIMIT", "1000"))
PORT = int(os.environ.get("PORT", "8001"))

app = FastAPI(title="burstops dummy-serverless")

_cold = {"started": False}


def prime_sieve(limit: int) -> list[int]:
    is_prime = bytearray([1]) * (limit + 1)
    is_prime[0] = is_prime[1] = 0
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i * i :: i] = bytearray(len(is_prime[i * i :: i]))
    return [i for i in range(2, limit + 1) if is_prime[i]]


@app.get("/health")
async def health():
    return {"status": "ok", "warm": _cold["started"]}


@app.api_route("/calculate", methods=["GET", "POST"])
@app.api_route("/api/twin/compute", methods=["GET", "POST"])
async def calculate(request: Request):
    body = await request.body()
    h = request.headers

    try:
        verify_request(
            secret=GATEWAY_HMAC_SECRET,
            expected_function_key=FUNCTION_KEY,
            provided_function_key=h.get("x-functions-key"),
            timestamp=h.get("x-gateway-timestamp"),
            signature=h.get("x-gateway-signature"),
            body=body,
            max_skew_seconds=MAX_CLOCK_SKEW,
        )
    except SignatureError as exc:
        logger.warning("rejected request: %s", exc.reason)
        raise HTTPException(status_code=exc.status_code, detail=exc.reason)

    # Novelty 2: Speculative Pre-Warm Ping Handler
    is_prewarm = (
        h.get("x-burstops-prewarm", "").lower() == "true"
        or request.query_params.get("prewarm") == "true"
    )
    if is_prewarm:
        _cold["started"] = True
        return JSONResponse(
            {
                "status": "WARM_READY",
                "instance_id": socket.gethostname()[:8],
                "prewarmed": True,
                "source": "serverless",
                "impl": "dummy-serverless",
            }
        )

    cold_start = not _cold["started"]
    _cold["started"] = True

    injected_ms = random.uniform(MIN_LATENCY_MS, MAX_LATENCY_MS)
    await asyncio.sleep(injected_ms / 1000.0)

    # Check for Digital Twin payload
    body_json = {}
    if body:
        try:
            body_json = json.loads(body.decode("utf-8"))
        except Exception:
            body_json = {}

    query_params = dict(request.query_params)
    for k, v in query_params.items():
        if k not in body_json:
            body_json[k] = v

    if "subsystem" in body_json or "twin_id" in body_json:
        result = await asyncio.to_thread(
            execute_digital_twin_workload, body_json, "AZURE_SERVERLESS_FUNCTION"
        )
        result["injected_latency_ms"] = round(injected_ms, 1)
        result["cold_start"] = cold_start
        return JSONResponse(result)

    primes = prime_sieve(PRIME_LIMIT)
    return JSONResponse(
        {
            "source": "serverless",
            "impl": "dummy-serverless",
            "executed_by": "AZURE_SERVERLESS_FUNCTION",
            "hostname": socket.gethostname(),
            "instance_id": socket.gethostname()[:8],
            "prime_count": len(primes),
            "prime_sum": sum(primes),
            "injected_latency_ms": round(injected_ms, 1),
            "cold_start": cold_start,
        }
    )
