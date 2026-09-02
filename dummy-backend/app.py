"""dummy-backend — stands in for an AKS pod.

Generates genuine, non-trivial CPU work (prime sieve / burn loop) so cAdvisor
can measure it. Response keys: source, hostname, prime_count, prime_sum.
"""
import socket
import time
from itertools import count, islice

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="burstops dummy-backend")


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
    return {"status": "ok"}


@app.api_route("/calculate", methods=["GET", "POST"])
async def calculate():
    primes = prime_sieve(1000)
    return JSONResponse(
        {
            "source": "k8s",
            "impl": "dummy-backend",
            "hostname": socket.gethostname(),
            "prime_count": len(primes),
            "prime_sum": sum(primes),
        }
    )


@app.post("/burn-cpu")
async def burn_cpu(ms: int = Query(default=500, ge=1, le=30000)):
    """Busy-loop doing floating-point arithmetic for exactly `ms` milliseconds.

    Deterministic knob for demos: organic traffic alone may not reliably
    saturate a 1.0-CPU-capped container, so /burn-cpu gives a reliable way
    to cross the 80% threshold on demand.
    """
    deadline = time.perf_counter() + ms / 1000.0
    x = 1.0000001
    while time.perf_counter() < deadline:
        for _ in range(1000):
            x = x * 1.0000001 + 0.0000001
    return {"status": "burned", "ms": ms, "x": x}
