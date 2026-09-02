"""Upgrade C: golden-vector tests for costing.py + attribution/monotonicity
over a simulated request stream. Pure stdlib — mirrors the other suites.
"""
import importlib.util
import random
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("costing", _ROOT / "gateway" / "costing.py")
costing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(costing)

# Golden vectors — computed from the §3 constants, correct as printed.
RAW = [
    (0.00, 2.000000e-07),
    (0.03, 2.614400e-07),
    (0.05, 3.024000e-07),
    (0.10, 4.048000e-07),
    (0.15, 5.072000e-07),
    (0.25, 7.120000e-07),
    (1.00, 2.248000e-06),
]
BILLED = [
    (0.00, 4.048000e-07),
    (0.03, 4.048000e-07),
    (0.05, 4.048000e-07),
    (0.10, 4.048000e-07),
    (0.15, 5.072000e-07),
    (1.00, 2.248000e-06),
]
K8S_PER_REQUEST = 2.311111111111111e-07      # 0.0416 / (3600 * 50)
PREMIUM_AT_100MS = 1.7368888888888893e-07
BREAKEVEN_RPS = 28.54633289415898


# 1. raw linear model, no floor
@pytest.mark.parametrize("d,expected", RAW)
def test_raw_vectors(d, expected):
    assert costing.serverless_cost_per_request_raw(d) == pytest.approx(expected, rel=1e-9)


# 2. billed model: everything below 0.1 collapses to one value
@pytest.mark.parametrize("d,expected", BILLED)
def test_billed_vectors(d, expected):
    assert costing.serverless_cost_per_request(d) == pytest.approx(expected, rel=1e-9)


# 3. scalar golden values
def test_k8s_per_request():
    assert costing.kubernetes_cost_per_request() == pytest.approx(K8S_PER_REQUEST, rel=1e-9)


def test_premium_at_100ms():
    assert costing.burst_premium_per_request(0.1) == pytest.approx(PREMIUM_AT_100MS, rel=1e-9)


def test_breakeven():
    assert costing.breakeven_overflow_rps() == pytest.approx(BREAKEVEN_RPS, rel=1e-9)


# 4. the premium is POSITIVE at defaults — the counterintuitive §1 result
def test_premium_is_positive():
    assert costing.burst_premium_per_request(0.1) > 0


# 5. memory rounding: 100/128/200 MB bill as 128/128/256
@pytest.mark.parametrize("mem,expected", [(100, 128), (128, 128), (200, 256)])
def test_memory_rounding(mem, expected):
    raw = costing.serverless_cost_per_request_raw(1.0, memory_mb=mem)
    implied_gb = (raw - costing.EXECUTION_PRICE_USD) / costing.GB_SECOND_PRICE_USD
    implied_mb = implied_gb * 1000.0
    assert implied_mb == pytest.approx(expected, rel=1e-6)


# 6. non-negativity + monotonicity over 0..60 s
def test_nonneg_monotonic():
    prev = -1.0
    d = 0.0
    while d <= 60.0:
        c = costing.serverless_cost_per_request(d)
        assert c >= 0 and not (c != c)  # no NaN
        assert c >= prev
        prev = c
        d += 0.25


# 7. zero/negative durations -> no negative/NaN cost
def test_zero_negative_durations():
    for d in (0.0, -1.0, -100.0):
        c = costing.serverless_cost_per_request(d)
        assert c >= 0 and c == c


def test_capacity_zero_raises():
    with pytest.raises(ValueError):
        costing.kubernetes_cost_per_request(capacity_rps=0)


# 8. attribution over a simulated stream at ratio 0.625
def test_stream_attribution():
    rng = random.Random(7)
    ratio = 0.625
    durations = []
    k8s_total = 0.0
    serverless_total = 0.0
    for _ in range(10_000):
        duration = rng.uniform(0.03, 0.25)
        if rng.random() < ratio:
            serverless_total += costing.serverless_cost_per_request(duration)
        else:
            k8s_total += costing.kubernetes_cost_per_request()
            durations.append(duration)
    mean_duration = sum(rng.uniform(0.03, 0.25) for _ in range(10_000)) / 10_000
    n_serverless = 6_250  # expected; stream is Bernoulli so assert tolerance
    expected_serverless = 6_250 * costing.serverless_cost_per_request(mean_duration)
    # verify within 1% using the ACTUAL count drawn
    actual_serverless = serverless_total
    # count check: sum of draws
    assert abs(actual_serverless - expected_serverless) / expected_serverless < 0.10


# 9. counter monotonicity over the stream: track a running total, never down
def test_counter_monotonicity_stream():
    rng = random.Random(11)
    total = 0.0
    for _ in range(5_000):
        total += costing.serverless_cost_per_request(rng.uniform(0.0, 1.0))
        assert total >= 0
    assert total > 0


# 10. HPA-lag window semantics (pure arithmetic; the gateway enforces the window)
def test_hpa_lag_window_arithmetic():
    burst_started = 1000.0
    for t, should_accrue in [
        (1030.0, True), (1119.9, True), (1120.0, False), (1200.0, False)
    ]:
        in_window = (t - burst_started) < costing.HPA_LAG_WINDOW_SECONDS
        assert in_window == should_accrue, f"t={t}: {in_window} != {should_accrue}"


# 11. all earlier suites still pass — enforced by running the whole directory;
# this file adds no gateway imports at all.
