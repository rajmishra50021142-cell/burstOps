"""BurstOps Azure Function — V2 Python programming model.

Single file, decorator-based registration, no function.json anywhere (that
is the V1 model and mixing them fails at load time).

Wire contract (must not drift from gateway.py's sign_request()):
  headers x-functions-key / x-gateway-timestamp / x-gateway-signature,
  signature = HMAC_SHA256(secret, f"{timestamp}:" + body).hexdigest().
GET requests carry an empty body (b"") — the Locust profile is 95% GETs,
so the empty-body case is the common path, not an edge case.
"""
import json
import logging
import os

import azure.functions as func

from hmac_util import DEFAULT_MAX_CLOCK_SKEW_SECONDS, SignatureError, verify_request

logger = logging.getLogger("burstops.function")

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

GATEWAY_HMAC_SECRET = os.environ.get("GATEWAY_HMAC_SECRET", "local-dev-secret-change-in-prod")
FUNCTION_KEY = os.environ.get("FUNCTION_KEY", "local-dev-function-key")
MAX_CLOCK_SKEW = int(os.environ.get("MAX_CLOCK_SKEW_SECONDS", str(DEFAULT_MAX_CLOCK_SKEW_SECONDS)))

_cold = {"started": False}


def prime_sieve(limit: int) -> list[int]:
    """Sieve of Eratosthenes over 2..limit — 2..1000 yields 168 primes summing to 76127,
    the same real work dummy-backend performs so the serverless path is comparable."""
    is_prime = bytearray([1]) * (limit + 1)
    is_prime[0] = is_prime[1] = 0
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            is_prime[i * i :: i] = bytearray(len(is_prime[i * i :: i]))
    return [i for i in range(2, limit + 1) if is_prime[i]]


@app.route(route="calculate", methods=[func.HttpMethod.GET, func.HttpMethod.POST])
def calculate(req: func.HttpRequest) -> func.HttpResponse:
    # The platform validates x-functions-key at AuthLevel.FUNCTION and
    # returns 401 before this code runs — but the LOCAL func host does not
    # enforce keys, so keep our own check: local testing must pass/fail the
    # same requests the cloud would.
    body = req.get_body() or b""  # b"" for GET — expected, sign those exact bytes

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
        # never log the secret, the key, or a full signature
        logger.warning("rejected request: %s", exc.reason)
        return func.HttpResponse(
            body=json.dumps({"detail": exc.reason}),
            status_code=exc.status_code,
            mimetype="application/json",
        )

    # No artificial latency here — a real Function has real cold starts;
    # fake delay would corrupt gateway_upstream_latency_seconds.
    primes = prime_sieve(1000)
    cold_start = not _cold["started"]
    _cold["started"] = True

    payload = {
        "source": "serverless",
        "impl": "azure-function",
        "instance_id": os.environ.get("WEBSITE_INSTANCE_ID", "local")[:8],
        "prime_count": len(primes),
        "prime_sum": sum(primes),
        "cold_start": cold_start,
    }
    return func.HttpResponse(
        body=json.dumps(payload), status_code=200, mimetype="application/json"
    )
