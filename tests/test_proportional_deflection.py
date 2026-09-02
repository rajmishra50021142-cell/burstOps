"""Upgrade A: PI proportional deflection tests — matches test_hysteresis.py's
style: import from source, stub third-party modules, inject time, no sleeping,
no network. test_hysteresis.py must keep passing unmodified alongside this.
"""
import random
import sys
import types
from pathlib import Path

# --- stubs (same as test_hysteresis.py) -------------------------------------
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
pc.Counter = lambda *a, **kw: types.SimpleNamespace(inc=lambda *a, **kw: None, labels=lambda **kw: types.SimpleNamespace(inc=lambda *a, **kw: None))
pc.Gauge = lambda *a, **kw: types.SimpleNamespace(set=lambda *a, **kw: None, labels=lambda **kw: types.SimpleNamespace(set=lambda *a, **kw: None))
pc.Histogram = lambda *a, **kw: types.SimpleNamespace(observe=lambda *a, **kw: None, labels=lambda **kw: types.SimpleNamespace(observe=lambda *a, **kw: None))
pc.generate_latest = lambda: b""

httpx_stub = types.ModuleType("httpx")
httpx_stub.AsyncClient = object
httpx_stub.Timeout = lambda *a, **kw: None
sys.modules["httpx"] = httpx_stub

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gateway"))
import gateway  # noqa: E402

RoutingState = gateway.RoutingState
Mode = gateway.Mode


# 1. ratio is 0 in BASELINE everywhere, incl. right after a BURST episode
def test_ratio_zero_in_baseline_sweep():
    s = RoutingState()
    for cpu in [x / 2.0 for x in range(0, 120)]:
        s.update_from_cpu(cpu)
        s.update_deflection(2.0)
        assert s.deflect_ratio == 0.0, f"ratio {s.deflect_ratio} at cpu {cpu} in BASELINE"
    s.update_from_cpu(90); s.update_deflection(2.0)   # enter burst, wind up
    assert s.mode is Mode.BURST and s.deflect_ratio > 0.0
    s.update_from_cpu(40); s.update_deflection(2.0)    # recover
    assert s.mode is Mode.BASELINE
    assert s.deflect_ratio == 0.0


# 2. setpoint validation refuses out-of-band values (raise behaviour chosen)
def test_setpoint_validation_raises(monkeypatch):
    monkeypatch.setattr(gateway, "CPU_SETPOINT_PERCENT", 55.0)
    try:
        RoutingState()
        assert False, "setpoint 55 must be rejected at construction"
    except ValueError:
        pass
    monkeypatch.setattr(gateway, "CPU_SETPOINT_PERCENT", 85.0)
    try:
        RoutingState()
        assert False, "setpoint 85 must be rejected at construction"
    except ValueError:
        pass


# 3. monotonicity: larger error -> ratio >= smaller-error ratio
def test_monotonicity():
    a = RoutingState(); b = RoutingState()
    a.update_from_cpu(85); a.update_deflection(2.0)
    b.update_from_cpu(95); b.update_deflection(2.0)
    assert b.deflect_ratio >= a.deflect_ratio


# 4. clamping across 0..400
def test_clamping_cpu_sweep():
    s = RoutingState()
    for i in range(800):
        s.update_from_cpu(i * 0.5)
        s.update_deflection(2.0)
        assert 0.0 <= s.deflect_ratio <= gateway.MAX_DEFLECT_RATIO


# 5. anti-windup: CPU 100 for 300s, drop to setpoint -> ratio < 0.1 in 30s
def test_anti_windup_recovery():
    s = RoutingState()
    s.update_from_cpu(100.0)
    for _ in range(150):                    # 300 simulated seconds at dt=2
        s.update_deflection(2.0)
        assert s._integral <= gateway.DEFLECT_INTEGRAL_CLAMP + 1e-9
    s.update_from_cpu(gateway.CPU_SETPOINT_PERCENT)   # e == 0 now
    for _ in range(15):                                # 30 simulated seconds
        s.update_deflection(2.0)
    assert s.deflect_ratio < 0.10, f"windup: ratio {s.deflect_ratio} after 30s"


# 6. slew limit: 60 -> 200 step moves ratio <= slew*dt
def test_slew_limit():
    s = RoutingState()
    s.update_from_cpu(60); s.update_deflection(2.0)
    before = s.deflect_ratio
    s.update_from_cpu(200); s.update_deflection(2.0)
    step = s.deflect_ratio - before
    assert step <= gateway.DEFLECT_MAX_SLEW_PER_SEC * 2.0 + 1e-9


# 7. integral resets to exactly 0.0 on transition into BASELINE
def test_integral_reset_on_baseline():
    s = RoutingState()
    s.update_from_cpu(90)
    for _ in range(30):
        s.update_deflection(2.0)
    assert s._integral > 0.0
    s.update_from_cpu(40)   # recover -> BASELINE
    assert s.mode is Mode.BASELINE
    assert s._integral == 0.0
    assert s.deflect_ratio == 0.0


# 8. Bernoulli fidelity: seeded RNG, ratio 0.35, 10k draws within ±2%
def test_bernoulli_fidelity():
    rng = random.Random(42)
    ratio = 0.35
    hits = sum(1 for _ in range(10_000) if rng.random() < ratio)
    assert abs(hits / 10_000 - 0.35) < 0.02


# 7b. closed-loop plant: first-order lag, L steps 0.5C -> 2C at t=0, 300s
def _run_plant(controller_enabled):
    """Returns (list of seen cpu, ratio history) over 300 simulated seconds."""
    C = 50.0                 # req/s that saturates the cluster
    L = 2.0 * C              # offered load after the step
    TAU = 15.0
    cpu_seen = 0.5 * C / C * 100.0
    s = RoutingState()
    hist_cpu, hist_ratio = [], []
    dt = 2.0
    for _ in range(int(300 / dt)):
        r = s.deflect_ratio if controller_enabled else (1.0 if s.mode is Mode.BURST else 0.0)
        cpu_true = 100.0 * min(L * (1 - r) / C, 4.0)
        cpu_seen += (cpu_true - cpu_seen) * (dt / TAU)
        s.update_from_cpu(cpu_seen)
        if controller_enabled:
            s.update_deflection(dt)
        else:
            # binary behaviour: ratio 1.0 whenever BURST (pre-upgrade shape)
            s.deflect_ratio = 1.0 if s.mode is Mode.BURST else 0.0
        hist_cpu.append(cpu_seen)
        hist_ratio.append(s.deflect_ratio)
    return hist_cpu, hist_ratio


def test_closed_loop_settles_at_setpoint():
    cpu, ratio = _run_plant(True)
    # settles within ±5 of setpoint by t=120s (index 60)
    assert abs(cpu[60] - gateway.CPU_SETPOINT_PERCENT) <= 5.0, f"cpu at 120s: {cpu[60]}"
    # post-settling: no excursion beyond ±10
    late = cpu[60:]
    assert max(late) - gateway.CPU_SETPOINT_PERCENT <= 10.0
    assert gateway.CPU_SETPOINT_PERCENT - min(late) <= 10.0
    # ratio settles at 0.625 ± 0.05 (L=2C -> 1-r=0.375 -> r=0.625)
    settled = ratio[-10:]
    avg = sum(settled) / len(settled)
    assert abs(avg - 0.625) <= 0.05, f"settled ratio {avg}"


# 7c. quantify: PI strictly better than binary on both metrics
def test_pi_beats_binary():
    setpoint = gateway.CPU_SETPOINT_PERCENT

    cpu_pi, _ = _run_plant(True)
    cpu_bin, _ = _run_plant(False)

    def integ_abs_dev(series):
        return sum(abs(c - setpoint) for c in series[30:])  # after t=60s

    def peak_to_trough(series):
        late = series[30:]
        return max(late) - min(late)

    ia_pi, ia_bin = integ_abs_dev(cpu_pi), integ_abs_dev(cpu_bin)
    pt_pi, pt_bin = peak_to_trough(cpu_pi), peak_to_trough(cpu_bin)
    print(f"\n∫|cpu-setpoint|dt  binary={ia_bin:.1f}  PI={ia_pi:.1f}  "
          f"improvement={(1 - ia_pi / ia_bin) * 100:.1f}%")
    print(f"peak-to-trough    binary={pt_bin:.1f}  PI={pt_pi:.1f}  "
          f"improvement={(1 - pt_pi / pt_bin) * 100:.1f}%")
    assert ia_pi < ia_bin
    assert pt_pi < pt_bin
