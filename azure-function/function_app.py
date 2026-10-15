"""BurstOps Azure Function — V2 Python programming model.

Single file, decorator-based registration, no function.json anywhere.
Wire contract (must not drift from gateway.py's sign_request()):
  headers x-functions-key / x-gateway-timestamp / x-gateway-signature,
  signature = HMAC_SHA256(secret, f"{timestamp}:" + body).hexdigest().

Supports:
- Novelty 2: Speculative Pre-Warming (X-BurstOps-Prewarm: true)
- Digital Twin Physics Engine (MONTE_CARLO_RUL, ROTOR_FFT_HARMONICS, THERMAL_STATE_CHECK)
- Legacy /calculate prime sieve backwards-compatibility
"""
import json
import logging
import os

import azure.functions as func

from digital_twin import execute_digital_twin_workload
from hmac_util import DEFAULT_MAX_CLOCK_SKEW_SECONDS, SignatureError, verify_request

logger = logging.getLogger("burstops.function")

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

GATEWAY_HMAC_SECRET = os.environ.get("GATEWAY_HMAC_SECRET", "local-dev-secret-change-in-prod")
FUNCTION_KEY = os.environ.get("FUNCTION_KEY", "local-dev-function-key")
MAX_CLOCK_SKEW = int(os.environ.get("MAX_CLOCK_SKEW_SECONDS", str(DEFAULT_MAX_CLOCK_SKEW_SECONDS)))

_cold = {"started": False}


def prime_sieve(limit: int) -> list[int]:
    """Sieve of Eratosthenes over 2..limit — 2..1000 yields 168 primes summing to 76127."""
    is_prime = bytearray([1]) * (limit + 1)
    is_prime[0] = is_prime[1] = 0
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i * i :: i] = bytearray(len(is_prime[i * i :: i]))
    return [i for i in range(2, limit + 1) if is_prime[i]]


@app.route(route="calculate", methods=[func.HttpMethod.GET, func.HttpMethod.POST])
def calculate(req: func.HttpRequest) -> func.HttpResponse:
    body = req.get_body() or b""

    try:
        verify_request(
            secret=GATEWAY_HMAC_SECRET,
            expected_function_key=FUNCTION_KEY,
            provided_function_key=req.headers.get("x-functions-key"),
            timestamp=req.headers.get("x-gateway-timestamp"),
            signature=req.headers.get("x-gateway-signature"),
            body=body,
            max_skew_seconds=MAX_CLOCK_SKEW,
        )
    except SignatureError as exc:
        logger.warning("rejected request: %s", exc.reason)
        return func.HttpResponse(
            body=json.dumps({"detail": exc.reason}),
            status_code=exc.status_code,
            mimetype="application/json",
        )

    # Novelty 2: Speculative Pre-Warm Ping Handler
    is_prewarm = (
        req.headers.get("x-burstops-prewarm", "").lower() == "true"
        or req.params.get("prewarm") == "true"
    )
    if is_prewarm:
        _cold["started"] = True
        return func.HttpResponse(
            body=json.dumps(
                {
                    "status": "WARM_READY",
                    "instance_id": os.environ.get("WEBSITE_INSTANCE_ID", "local")[:8],
                    "prewarmed": True,
                    "source": "serverless",
                    "impl": "azure-function",
                }
            ),
            status_code=200,
            mimetype="application/json",
        )

    cold_start = not _cold["started"]
    _cold["started"] = True

    # Parse JSON body for Digital Twin payload
    body_json = {}
    if body:
        try:
            body_json = json.loads(body.decode("utf-8"))
        except Exception:
            body_json = {}

    for k, v in req.params.items():
        if k not in body_json:
            body_json[k] = v

    if "subsystem" in body_json or "twin_id" in body_json:
        payload = execute_digital_twin_workload(body_json, "AZURE_SERVERLESS_FUNCTION")
        payload["cold_start"] = cold_start
        return func.HttpResponse(
            body=json.dumps(payload), status_code=200, mimetype="application/json"
        )

    primes = prime_sieve(1000)
    payload = {
        "source": "serverless",
        "impl": "azure-function",
        "executed_by": "AZURE_SERVERLESS_FUNCTION",
        "instance_id": os.environ.get("WEBSITE_INSTANCE_ID", "local")[:8],
        "prime_count": len(primes),
        "prime_sum": sum(primes),
        "cold_start": cold_start,
    }
    return func.HttpResponse(
        body=json.dumps(payload), status_code=200, mimetype="application/json"
    )
