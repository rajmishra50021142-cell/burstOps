import os
import sys
import time
from pathlib import Path
import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "gateway"))

import golden_trio
from backend.digital_twin import (
    execute_digital_twin_workload,
    estimate_compute_time_ms,
    calculate_semantic_gamma,
    GAMMA_THRESHOLD,
    OVERHEAD_MS,
)

AIMDThresholdController = golden_trio.AIMDThresholdController
PredictivePrewarmer = golden_trio.PredictivePrewarmer
update_load_velocity = golden_trio.update_load_velocity
get_routing_decision_for_gamma = golden_trio.get_routing_decision_for_gamma
MAX_BASE_COMPUTE_SLOTS = golden_trio.MAX_BASE_COMPUTE_SLOTS


def test_digital_twin_physics_monte_carlo():
    """Verify Monte Carlo RUL computation and execution provenance fields."""
    payload = {
        "twin_id": "WT-TEST-01",
        "subsystem": "MONTE_CARLO_RUL",
        "rpm": 1850.0,
        "temperature_c": 75.0,
        "vibration_amplitude": 0.08,
        "monte_carlo_iterations": 20000,
    }
    result = execute_digital_twin_workload(payload, "AKS_BASE_POD")

    assert result["twin_id"] == "WT-TEST-01"
    assert result["subsystem"] == "MONTE_CARLO_RUL"
    assert result["executed_by"] == "AKS_BASE_POD"
    assert "node_hostname" in result
    assert "process_pid" in result
    assert result["cpu_time_ms"] >= 0.0
    assert result["wall_time_ms"] >= 0.0

    # Physics output verification
    physics = result["physics_output"]
    assert "failure_probability" in physics
    assert 0.0 <= physics["failure_probability"] <= 1.0
    assert "mean_health_index" in physics
    assert len(physics["verification_hash"]) == 64

    # Backward compatibility with cryptographic prime sieve canaries
    assert result["prime_count"] == 168
    assert result["prime_sum"] == 76127


def test_digital_twin_physics_rotor_fft():
    """Verify Rotor FFT harmonics computation."""
    payload = {
        "twin_id": "WT-TEST-02",
        "subsystem": "ROTOR_FFT_HARMONICS",
        "rpm": 2100.0,
        "temperature_c": 80.0,
        "vibration_amplitude": 0.12,
    }
    result = execute_digital_twin_workload(payload, "AZURE_SERVERLESS_FUNCTION")

    assert result["subsystem"] == "ROTOR_FFT_HARMONICS"
    assert result["executed_by"] == "AZURE_SERVERLESS_FUNCTION"
    physics = result["physics_output"]
    assert "peak_harmonic_hz" in physics
    assert physics["peak_harmonic_hz"] > 0.0
    assert "peak_magnitude" in physics
    assert len(physics["verification_hash"]) == 64


def test_digital_twin_physics_thermal_state_check():
    """Verify thermal equilibrium check execution."""
    payload = {
        "twin_id": "WT-TEST-03",
        "subsystem": "THERMAL_STATE_CHECK",
        "rpm": 1200.0,
        "temperature_c": 65.0,
        "ambient_temp_c": 28.0,
    }
    result = execute_digital_twin_workload(payload, "AKS_BASE_POD")

    assert result["subsystem"] == "THERMAL_STATE_CHECK"
    physics = result["physics_output"]
    assert "stator_equilibrium_temp_c" in physics
    assert "thermal_stress_index" in physics
    assert len(physics["verification_hash"]) == 64


def test_semantic_gamma_ratio_classification():
    """Verify Novelty 3: Compute-to-Communication ratio γ calculation."""
    # Monte Carlo has high compute relative to ~60ms overhead
    mc_gamma, mc_est = calculate_semantic_gamma({"subsystem": "MONTE_CARLO_RUL", "monte_carlo_iterations": 200000})
    assert mc_gamma >= GAMMA_THRESHOLD
    assert mc_gamma > 5.0

    # FFT has medium-high compute
    fft_gamma, fft_est = calculate_semantic_gamma({"subsystem": "ROTOR_FFT_HARMONICS"})
    assert fft_gamma >= GAMMA_THRESHOLD
    assert fft_gamma > 4.0

    # Thermal check has very low compute (< 40ms)
    thermal_gamma, thermal_est = calculate_semantic_gamma({"subsystem": "THERMAL_STATE_CHECK"})
    assert thermal_gamma < GAMMA_THRESHOLD
    assert thermal_gamma < 1.0


def test_semantic_routing_decisions():
    """Verify asymmetric routing decisions based on gamma."""
    # Low gamma tasks are pinned to AKS when capacity allows
    decision_low, reason_low = get_routing_decision_for_gamma(
        gamma=0.42,
        composite_utilization=85.0,
        base_deflect_ratio=0.5,
    )
    assert decision_low == "k8s"
    assert reason_low == "PINNED_AKS_LOW_GAMMA"

    # High gamma tasks in burst mode deflect to serverless
    decision_high, reason_high = get_routing_decision_for_gamma(
        gamma=9.2,
        composite_utilization=85.0,
        base_deflect_ratio=0.8,
    )
    assert decision_high in ("k8s", "serverless")
    assert reason_high in ("DEFLECTED_SERVERLESS_HIGH_GAMMA", "BASELINE_K8S_HIGH_GAMMA")


def test_aimd_threshold_controller():
    """Verify Novelty 1: AIMD self-tuning threshold controller."""
    controller = AIMDThresholdController(
        target_p95_ms=650.0,
        initial_theta=0.80,
        min_theta=0.60,
        max_theta=0.92,
    )

    assert controller.current_theta == 0.80

    # Case 1: Tail latency SLO breach (p95 = 750ms > 650ms) -> Multiplicative Decrease
    latencies_slow = [750.0] * 35
    new_theta = controller.update(latencies_slow)
    assert new_theta < 0.80
    assert pytest.approx(new_theta, rel=1e-3) == 0.80 * 0.92
    assert controller.last_direction == "DECREASE"

    # Multiple violations should not drop below min_theta (0.60)
    for _ in range(10):
        controller.update(latencies_slow)
    assert controller.current_theta >= 0.60

    # Case 2: Fast execution (p95 = 200ms < 0.65 * 650ms) after cooldown -> Additive Increase
    latencies_fast = [200.0] * 35
    current = controller.current_theta
    # Advance time past 15-second violation cooldown
    new_theta_fast = controller.update(latencies_fast, now=time.time() + 25.0)
    assert new_theta_fast > current
    assert pytest.approx(new_theta_fast, rel=1e-3) == current + 0.01


def test_predictive_prewarmer_velocity_and_breach():
    """Verify Novelty 2: dU/dt velocity and estimated time to breach."""
    prewarmer = PredictivePrewarmer(
        velocity_trigger_pct_per_s=5.0,
        time_to_breach_trigger_s=4.0,
        cooldown_s=30.0,
    )

    t0 = 1000.0
    # Sample at t0: 50%
    vel1, t_breach1 = prewarmer.update_load_velocity(50.0, t0, current_theta=0.80)
    assert vel1 == 0.0

    # Sample at t0 + 2.0s: 66% (dU = +16% over 2s = +8.0%/s)
    vel2, t_breach2 = prewarmer.update_load_velocity(66.0, t0 + 2.0, current_theta=0.80)
    assert vel2 >= 7.0
    # Remaining to 80% is 14%. At 8%/s, breach time is 14 / 8 = 1.75s
    assert t_breach2 is not None
    assert 0 < t_breach2 <= 4.0

    # Check trigger condition
    should_fire = prewarmer.should_trigger_prewarm(
        current_u=66.0,
        current_theta=0.80,
        velocity_pct_per_s=vel2,
        t_breach_s=t_breach2,
        now=t0 + 2.0,
    )
    assert should_fire is True


def test_capacity_model_definitions():
    """Verify explicit capacity modeling and slot constants."""
    assert MAX_BASE_COMPUTE_SLOTS == 10
    # 80% threshold = 8 slots
    threshold_slots = MAX_BASE_COMPUTE_SLOTS * 0.80
    assert threshold_slots == 8.0
