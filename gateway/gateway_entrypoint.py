"""Env-var shim: imports gateway.py, patches its module-level constants from
environment variables at process startup, then launches uvicorn.

Deliberate design: gateway.py stays a read-only spec file. All runtime
configuration flows through here. Preserve this pattern — don't collapse the
two files, and don't try to bypass the shim with different env var names.
"""
import logging
import os
import sys

import gateway

log = logging.getLogger("burstops.entrypoint")


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


gateway.PROMETHEUS_URL = _env("PROMETHEUS_URL", gateway.PROMETHEUS_URL)
gateway.K8S_UPSTREAM = _env("K8S_UPSTREAM", gateway.K8S_UPSTREAM)
gateway.FUNCTION_UPSTREAM = _env("FUNCTION_UPSTREAM", gateway.FUNCTION_UPSTREAM)
gateway.FUNCTION_KEY = _env("FUNCTION_KEY", gateway.FUNCTION_KEY)
gateway.GATEWAY_HMAC_SECRET = _env("GATEWAY_HMAC_SECRET", gateway.GATEWAY_HMAC_SECRET)

# Upgrade A: PI controller constants, patched with the same pattern.
for _name in (
    "CPU_SETPOINT_PERCENT",
    "DEFLECT_KP",
    "DEFLECT_KI",
    "MAX_DEFLECT_RATIO",
    "DEFLECT_MAX_SLEW_PER_SEC",
    "DEFLECT_INTEGRAL_CLAMP",
):
    _raw = os.environ.get(_name)
    if _raw not in (None, ""):
        setattr(gateway, _name, float(_raw))

# Upgrade B: build the Redis backplane AFTER constants are patched. Empty
# REDIS_URL (the default) => backplane off, single-replica behaviour.
try:
    import redis_backplane

    if gateway.GATEWAY_INSTANCE_ID:
        redis_backplane.GATEWAY_INSTANCE_ID = gateway.GATEWAY_INSTANCE_ID
    for _rb_name in ("REDIS_LEADER_TTL_MS", "REDIS_LEADER_RENEW_MS",
                     "REDIS_STATE_MAX_AGE_MS", "REDIS_SOCKET_TIMEOUT_S"):
        _raw = os.environ.get(_rb_name)
        if _raw not in (None, ""):
            setattr(redis_backplane, _rb_name, float(_raw.split(".")[0]) if _rb_name.endswith("_MS") else float(_raw))
    gateway._backplane = redis_backplane.build_backplane(gateway, gateway.routing_state)
    if gateway._backplane is not None:
        log.info("redis backplane enabled: %s", os.environ["REDIS_URL"])
    else:
        log.info("redis backplane disabled (no REDIS_URL)")
except Exception as exc:  # noqa: BLE001 — never crash the pod for a cache
    log.warning("redis backplane setup failed, running single-replica mode: %s", exc)
    gateway._backplane = None

log.info(
    "gateway configured: K8S_UPSTREAM=%s FUNCTION_UPSTREAM=%s PROMETHEUS_URL=%s",
    gateway.K8S_UPSTREAM, gateway.FUNCTION_UPSTREAM, gateway.PROMETHEUS_URL,
)

# Upgrade D: tracing is strictly opt-in (default exporter=none -> zero spans).
# Instrumentation attaches from OUTSIDE; gateway.py is never modified.
try:
    import tracing

    if tracing.configure_tracing() is not None:
        tracing.install_instrumentation(gateway.app)
        log.info("tracing enabled")
    else:
        log.info("tracing disabled (OTEL_TRACES_EXPORTER=none or unresolvable)")
except Exception as exc:  # noqa: BLE001 — a typo in env must not stop traffic
    log.warning("tracing setup failed, serving without it: %s", exc)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        gateway.app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        log_level="info",
    )
