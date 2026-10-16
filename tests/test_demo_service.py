import asyncio
import time
import pytest
from fastapi.testclient import TestClient

from backend.adapter import MockTrafficAdapter
from backend.config import settings
from backend.main import app, manager
from backend.manager import DemoRunManager, redact_text
from backend.models import ActionState


@pytest.fixture(autouse=True)
def setup_mock_environment():
    """Ensure every test runs with Mock settings and an isolated Mock adapter."""
    settings.DEMO_MODE = "mock"
    settings.COOLDOWN_SECONDS = 0
    settings.POLL_INTERVAL_SECONDS = 0.05
    settings.RECOVERY_POLL_INTERVAL_SECONDS = 0.05
    mock_adapter = MockTrafficAdapter()
    manager.adapter = mock_adapter
    manager.active_run = None
    manager.last_completed_run = None
    manager.last_run_end_time = 0.0
    yield
    if manager._current_task and not manager._current_task.done():
        manager._current_task.cancel()
    manager.active_run = None


def test_health_endpoint():
    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "burstops-demo-control"


def test_initial_status_ready():
    with TestClient(app) as client:
        resp = client.get("/api/demo/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "Ready"
        assert data["can_burst"] is True
        assert data["can_recover"] is False
        assert len(data["ordered_links"]) == 8


@pytest.mark.asyncio
async def test_successful_burst_initiation():
    run = await manager.start_burst()
    assert run.run_id.startswith("run-")
    assert run.state in (ActionState.STARTING, ActionState.RUNNING)

    status = await manager.get_status()
    assert status.can_burst is False
    assert status.active_run_id == run.run_id

    # Wait for mock lifecycle to transition through burst
    await asyncio.sleep(0.1)
    if manager._current_task and not manager._current_task.done():
        manager._current_task.cancel()


@pytest.mark.asyncio
async def test_rejection_of_duplicate_burst():
    run = await manager.start_burst()
    assert run is not None

    with pytest.raises(ValueError, match="already in progress"):
        await manager.start_burst()

    if manager._current_task and not manager._current_task.done():
        manager._current_task.cancel()


@pytest.mark.asyncio
async def test_recovery_lifecycle():
    run = await manager.start_burst()
    assert run.run_id is not None

    # Wait for mock to tick into burst
    for _ in range(10):
        await asyncio.sleep(0.05)
        if run.burst_detected:
            break

    # Now trigger recovery
    rec_run = await manager.start_recovery()
    assert rec_run.run_id == run.run_id
    assert rec_run.recovery_started is True

    # Wait for recovery to complete
    for _ in range(15):
        await asyncio.sleep(0.05)
        if run.baseline_verified or manager.active_run is None:
            break

    status = await manager.get_status()
    # Either active run marked baseline verified or completed
    assert run.baseline_verified is True or status.last_completed_run is not None


@pytest.mark.asyncio
async def test_rejection_of_recovery_when_no_active_run():
    assert manager.active_run is None
    with pytest.raises(ValueError, match="No active demonstration run"):
        await manager.start_recovery()


def test_api_burst_and_recover_flow():
    with TestClient(app) as client:
        # 1. Trigger burst
        resp = client.post("/api/demo/burst")
        assert resp.status_code == 200
        data = resp.json()
        run_id = data["run_id"]
        assert run_id.startswith("run-")

        # 2. Check status shows active run
        status_resp = client.get("/api/demo/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["active_run_id"] == run_id

        # 3. Duplicate burst is rejected with 409
        dup_resp = client.post("/api/demo/burst")
        assert dup_resp.status_code == 409

        # 4. Trigger recovery
        rec_resp = client.post("/api/demo/recover")
        assert rec_resp.status_code == 200
        assert rec_resp.json()["run_id"] == run_id


def test_api_recover_without_run_returns_400():
    with TestClient(app) as client:
        manager.active_run = None
        resp = client.post("/api/demo/recover")
        assert resp.status_code == 400


def test_get_run_detail():
    with TestClient(app) as client:
        # Non-existent run
        resp = client.get("/api/demo/runs/non-existent-id")
        assert resp.status_code == 404

        # Trigger burst and fetch
        burst_resp = client.post("/api/demo/burst")
        run_id = burst_resp.json()["run_id"]
        run_resp = client.get(f"/api/demo/runs/{run_id}")
        assert run_resp.status_code == 200
        assert run_resp.json()["run_id"] == run_id


def test_output_redaction():
    raw_text = "Connecting to Azure with code=secretValue123456789 and x-functions-key: mySecretKeyABCDEF123456"
    safe = redact_text(raw_text)
    assert "secretValue" not in safe
    assert "mySecretKey" not in safe
    assert "***REDACTED***" in safe


@pytest.mark.asyncio
async def test_cooldown_enforcement():
    settings.COOLDOWN_SECONDS = 10
    manager.last_run_end_time = time.time()
    with pytest.raises(ValueError, match="cooldown"):
        await manager.start_burst()


@pytest.mark.asyncio
async def test_adapter_failure_handling():
    class FailingAdapter(MockTrafficAdapter):
        async def start_traffic(self, log_cb):
            log_cb("ERROR", "Simulated connection refused to gateway")
            return False

    fail_mgr = DemoRunManager(adapter=FailingAdapter())
    run = await fail_mgr.start_burst()
    await asyncio.sleep(0.05)
    assert run.state == ActionState.FAILED
    assert "Failed to start" in run.error_message


def test_full_mocked_integration_flow():
    """Simulates the entire frontend-backend cycle in mock mode."""
    with TestClient(app) as client:
        # 1. Front page loads
        home_resp = client.get("/")
        assert home_resp.status_code == 200
        assert "BurstOps" in home_resp.text

        # 2. Check initial status
        st_resp = client.get("/api/demo/status")
        assert st_resp.status_code == 200
        assert st_resp.json()["can_burst"] is True

        # 3. User clicks Generate Traffic / Simulate Burst
        burst_resp = client.post("/api/demo/burst")
        assert burst_resp.status_code == 200
        run_id = burst_resp.json()["run_id"]

        # 4. Frontend polls status and sees active run
        poll_resp = client.get("/api/demo/status")
        assert poll_resp.json()["active_run_id"] == run_id

        # 5. User clicks Recover to Baseline
        rec_resp = client.post("/api/demo/recover")
        assert rec_resp.status_code == 200
        assert rec_resp.json()["run_id"] == run_id


def test_golden_trio_status_initial_zero_slots():
    """Verify that on startup, active slots drop to 0 / 10 instead of being stuck at 2."""
    with TestClient(app) as client:
        resp = client.get("/api/golden-trio/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "capacity_model" in data
        assert data["capacity_model"]["aks_base_capacity_slots"] == 10
        assert data["capacity_model"]["active_compute_slots"] == 0
        assert data["capacity_model"]["slot_saturation_pct"] == 0.0
        assert "novelty_1_aimd_threshold" in data
        assert "novelty_2_predictive_prewarm" in data
        assert "novelty_3_semantic_gamma" in data


def test_twin_compute_provenance_and_local_execution():
    """Verify /api/twin/compute baseline execution on AKS_BASE_POD and explicit provenance fields."""
    with TestClient(app) as client:
        payload = {
            "twin_id": "WT-UNIT-01",
            "subsystem": "MONTE_CARLO_RUL",
            "rpm": 1800,
            "temperature_c": 75,
            "monte_carlo_iterations": 10000,
        }
        resp = client.post("/api/twin/compute", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        # Required fields for ExecutionConsole.tsx
        assert data["executed_by"] == "AKS_BASE_POD"
        assert "cpu_time_ms" in data and data["cpu_time_ms"] >= 0.0
        assert "wall_time_ms" in data and data["wall_time_ms"] >= 0.0
        assert "verification_hash" in data and len(data["verification_hash"]) == 64
        assert "physics_output" in data
        assert data["physics_output"]["verification_hash"] == data["verification_hash"]
        assert data["route"] == "k8s"
        assert data["routing_reason"] == "BASELINE_K8S_NORMAL"
        assert "gamma_ratio" in data


def test_twin_compute_serverless_deflection_under_high_load():
    """Verify that when load exceeds threshold, high gamma workloads deflect to serverless."""
    with TestClient(app) as client:
        # Simulate active burst
        manager.adapter.is_running = True
        manager.adapter.cpu = 88.0
        manager.adapter.mode = "burst"

        payload = {
            "twin_id": "WT-UNIT-BURST",
            "subsystem": "MONTE_CARLO_RUL",
            "rpm": 2200,
            "temperature_c": 95,
            "monte_carlo_iterations": 200000,
        }
        resp = client.post("/api/twin/compute", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["executed_by"] == "AZURE_SERVERLESS_FUNCTION"
        assert data["route"] == "serverless"
        assert data["routing_reason"] == "DEFLECTED_SERVERLESS_HIGH_GAMMA"
        assert "verification_hash" in data
        assert data["gamma_ratio"] > 1.5


def test_twin_compute_low_gamma_pinned_under_high_load():
    """Verify that low gamma tasks (THERMAL_STATE_CHECK) stay pinned to AKS even under load."""
    with TestClient(app) as client:
        manager.adapter.is_running = True
        manager.adapter.cpu = 88.0
        manager.adapter.mode = "burst"

        payload = {
            "twin_id": "WT-UNIT-LOW-GAMMA",
            "subsystem": "THERMAL_STATE_CHECK",
            "temperature_c": 70,
        }
        resp = client.post("/api/twin/compute", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["executed_by"] == "AKS_BASE_POD"
        assert data["route"] == "k8s"
        assert data["routing_reason"] == "PINNED_AKS_LOW_GAMMA"
        assert data["gamma_ratio"] < 1.5


def test_gateway_shim_and_calculate_alias():
    """Verify that /gateway/ prefix requests and /calculate work seamlessly."""
    with TestClient(app) as client:
        resp = client.get("/gateway/api/golden-trio/status")
        assert resp.status_code == 200
        assert resp.json()["capacity_model"]["aks_base_capacity_slots"] == 10

        calc_resp = client.post("/calculate", json={"subsystem": "THERMAL_STATE_CHECK"})
        assert calc_resp.status_code == 200
        assert "verification_hash" in calc_resp.json()

