"""Dependency-free pytest suite for RoutingState hysteresis invariants.

Imports RoutingState and Mode directly from gateway.py — zero HTTP calls,
zero Docker required. Stubs fastapi, httpx and prometheus_client at module
level (gateway.py imports them at import time) with minimal fakes, so the
test process never needs the full runtime installed.

Six invariants asserted:
 1. Threshold crossing: BASELINE -> BURST exactly at 80%.
 2. Hysteresis band: no flip anywhere between 60-80%.
 3. Recovery: BURST -> BASELINE only below 60%.
 4. No-flapping guarantee under oscillation inside the band.
 5. Fail-safe grace period: stale data tolerated for 15s.
 6. Fail-open behavior: after the grace period, mode forces to BURST.
"""
import sys
import types
import uuid
from pathlib import Path

# --- stub third-party modules gateway.py imports at import time -----------
def _mkmod(name):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)
    return sys.modules[name]

_mkmod("fastapi")
_mkmod("fastapi.responses")
_mkmod("prometheus_client")

fastapi = sys.modules["fastapi"]
fastapi.FastAPI = lambda *a, **kw: types.SimpleNamespace(
    router=types.SimpleNamespace(lifespan_context=None),
    get=lambda *a, **kw: (lambda f: f),
    api_route=lambda *a, **kw: (lambda f: f),
    add_middleware=lambda *a, **kw: None,
)
fastapi.Request = object
fastapi.api_route = lambda *a, **kw: (lambda f: f)

responses = sys.modules["fastapi.responses"]
responses.JSONResponse = type("JSONResponse", (), {})
responses.PlainTextResponse = type("PlainTextResponse", (), {})

pc = sys.modules["prometheus_client"]
pc.CONTENT_TYPE_LATEST = "text/plain"
pc.Counter = lambda *a, **kw: types.SimpleNamespace(inc=lambda *a, **kw: None,
                                                    labels=lambda **kw: types.SimpleNamespace(inc=lambda *a, **kw: None))
pc.Gauge = lambda *a, **kw: types.SimpleNamespace(set=lambda *a, **kw: None,
                                                  labels=lambda **kw: types.SimpleNamespace(set=lambda *a, **kw: None))
pc.Histogram = lambda *a, **kw: types.SimpleNamespace(observe=lambda *a, **kw: None,
                                                      labels=lambda **kw: types.SimpleNamespace(observe=lambda *a, **kw: None))
pc.generate_latest = lambda: b""

httpx_stub = types.ModuleType("httpx")
httpx_stub.AsyncClient = object
httpx_stub.Timeout = lambda *a, **kw: None
sys.modules["httpx"] = httpx_stub

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gateway"))
import gateway  # noqa: E402

RoutingState = gateway.RoutingState
Mode = gateway.Mode


def _set_time(monkeypatch, value):
    monkeypatch.setattr(gateway.time, "time", lambda: value)


# 1. threshold crossing: BASELINE -> BURST exactly at 80
def test_burst_threshold_crossing():
    s = RoutingState()
    s.update_from_cpu(79.999)
    assert s.mode is Mode.BASELINE
    s.update_from_cpu(80.0)
    assert s.mode is Mode.BURST


# 2. hysteresis dead band: no flip anywhere in (60, 80)
def test_dead_band_no_flip():
    for cpu in (60.0, 65, 70, 75, 79, 79.999):
        s = RoutingState()
        s.update_from_cpu(cpu)
        assert s.mode is Mode.BASELINE, f"flipped at {cpu}"


# 3. recovery: BURST -> BASELINE only below 60
def test_recovery_below_sixty():
    s = RoutingState()
    s.update_from_cpu(85)
    assert s.mode is Mode.BURST
    s.update_from_cpu(60.0)          # exactly 60 is NOT below
    assert s.mode is Mode.BURST
    s.update_from_cpu(59.999)
    assert s.mode is Mode.BASELINE


# 4. no flapping under oscillation inside the band
def test_no_flap_oscillation():
    s = RoutingState()
    s.update_from_cpu(90)
    assert s.mode is Mode.BURST
    for cpu in (70, 78, 62, 75, 68, 71) * 3:
        s.update_from_cpu(cpu)
        assert s.mode is Mode.BURST, f"flapped at {cpu}"


# 5. fail-safe grace: stale data tolerated for <= 15s
def test_fail_safe_grace_period(monkeypatch):
    s = RoutingState()
    _set_time(monkeypatch, 1000.0)
    s.update_from_cpu(50)
    s.last_successful_poll = 1000.0
    _set_time(monkeypatch, 1010.0)   # 10s stale — within grace
    s.apply_fail_safe()
    assert s.mode is Mode.BASELINE


# 6. fail-open: past grace, forces to BURST
def test_fail_open_to_burst(monkeypatch):
    s = RoutingState()
    _set_time(monkeypatch, 1000.0)
    s.update_from_cpu(50)
    s.last_successful_poll = 1000.0
    _set_time(monkeypatch, 1016.0)  # 16s stale — past grace
    s.apply_fail_safe()
    assert s.mode is Mode.BURST
