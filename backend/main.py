import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.manager import DemoRunManager
from backend.models import (
    BurstTriggerResponse,
    DemoStatusResponse,
    RecoverTriggerResponse,
    RunDetail,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("burstops.main")

manager = DemoRunManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("BurstOps Demo Control Service starting (mode: %s)...", settings.DEMO_MODE)
    yield
    logger.info("BurstOps Demo Control Service shutting down...")
    if manager.active_run:
        await manager.adapter.cleanup()


app = FastAPI(
    title="BurstOps Demo Control Service",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local dev Vite proxying
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "burstops-demo-control",
        "mode": settings.DEMO_MODE,
        "target_gateway": settings.GATEWAY_BASE_URL,
    }


@app.get("/api/demo/status", response_model=DemoStatusResponse)
async def demo_status():
    return await manager.get_status()


@app.post("/api/demo/burst", response_model=BurstTriggerResponse)
async def trigger_burst():
    try:
        run = await manager.start_burst()
        return BurstTriggerResponse(
            run_id=run.run_id,
            status=run.state,
            message="Burst experiment started successfully.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@app.post("/api/demo/recover", response_model=RecoverTriggerResponse)
async def trigger_recovery():
    try:
        run = await manager.start_recovery()
        return RecoverTriggerResponse(
            run_id=run.run_id,
            status=run.state,
            message="Recovery to baseline initiated successfully.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@app.get("/api/demo/runs/{run_id}", response_model=RunDetail)
async def get_run_detail(run_id: str):
    run = await manager.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found.",
        )
    return run


@app.get("/api/golden-trio/status")
async def golden_trio_status():
    if settings.DEMO_MODE.lower() == "mock":
        mode, cpu = await manager.adapter.poll_health()
        return {
            "capacity_model": {
                "aks_base_capacity_slots": 10,
                "active_compute_slots": 8 if mode == "burst" else 2,
                "slot_saturation_pct": 80.0 if mode == "burst" else 20.0,
                "cpu_limit": "500m (0.5 vCPU)",
                "memory_limit": "512Mi",
                "composite_utilization_pct": round(cpu, 1),
                "explanation": "100% capacity = 10 concurrent heavy Digital Twin computations (or 500m vCPU). 80% threshold = 8 active compute slots (or 400m vCPU).",
            },
            "novelty_1_aimd_threshold": {
                "current_threshold_theta": 0.785,
                "current_threshold_pct": 78.5,
                "aks_p95_latency_ms": 580.0,
                "slo_target_p95_ms": 650.0,
                "bounds": [0.60, 0.92],
                "mode": mode,
            },
            "novelty_2_predictive_prewarm": {
                "load_velocity_pct_per_s": 5.8 if mode == "burst" else 0.4,
                "prewarm_state": "WARM_READY" if mode == "burst" else "IDLE",
                "prewarm_saves_count": 3,
                "velocity_trigger_pct_per_s": 5.0,
                "time_to_breach_trigger_s": 4.0,
            },
            "novelty_3_semantic_gamma": {
                "gamma_threshold": 1.5,
                "subsystems": {
                    "MONTE_CARLO_RUL": {"gamma": 9.17, "policy": "Deflect to Azure Serverless"},
                    "ROTOR_FFT_HARMONICS": {"gamma": 6.33, "policy": "Deflect to Azure Serverless"},
                    "THERMAL_STATE_CHECK": {"gamma": 0.42, "policy": "Pinned to AKS Base Server"},
                },
            },
        }
    else:
        import httpx

        client = httpx.AsyncClient(timeout=8.0)
        url = f"{settings.GATEWAY_BASE_URL.rstrip('/')}/api/golden-trio/status"
        try:
            resp = await client.get(url, timeout=8.0)
            return resp.json()
        except Exception:
            return {
                "capacity_model": {
                    "aks_base_capacity_slots": 10,
                    "active_compute_slots": 1,
                    "slot_saturation_pct": 10.0,
                    "cpu_limit": "500m (0.5 vCPU)",
                    "memory_limit": "512Mi",
                    "composite_utilization_pct": 15.0,
                    "explanation": "100% capacity = 10 concurrent heavy Digital Twin computations (or 500m vCPU). 80% threshold = 8 active compute slots (or 400m vCPU).",
                },
                "novelty_1_aimd_threshold": {
                    "current_threshold_theta": 0.80,
                    "current_threshold_pct": 80.0,
                    "aks_p95_latency_ms": 210.0,
                    "slo_target_p95_ms": 650.0,
                    "bounds": [0.60, 0.92],
                    "mode": "baseline",
                },
                "novelty_2_predictive_prewarm": {
                    "load_velocity_pct_per_s": 0.2,
                    "prewarm_state": "IDLE",
                    "prewarm_saves_count": 0,
                    "velocity_trigger_pct_per_s": 5.0,
                    "time_to_breach_trigger_s": 4.0,
                },
                "novelty_3_semantic_gamma": {
                    "gamma_threshold": 1.5,
                    "subsystems": {
                        "MONTE_CARLO_RUL": {"gamma": 9.17, "policy": "Deflect to Azure Serverless"},
                        "ROTOR_FFT_HARMONICS": {"gamma": 6.33, "policy": "Deflect to Azure Serverless"},
                        "THERMAL_STATE_CHECK": {"gamma": 0.42, "policy": "Pinned to AKS Base Server"},
                    },
                },
            }
        finally:
            await client.aclose()


@app.api_route("/api/twin/compute", methods=["GET", "POST"])
async def twin_compute(request: Request):
    import json

    body = await request.body()
    body_json = {}
    if body:
        try:
            body_json = json.loads(body.decode("utf-8"))
        except Exception:
            body_json = {}
    for k, v in request.query_params.items():
        if k not in body_json:
            body_json[k] = v

    if settings.DEMO_MODE.lower() == "mock":
        from backend.digital_twin import execute_digital_twin_workload

        mode, cpu = await manager.adapter.poll_health()
        exec_env = "AZURE_SERVERLESS_FUNCTION" if mode == "burst" else "AKS_BASE_POD"
        res = execute_digital_twin_workload(body_json, exec_env)
        sub = body_json.get("subsystem", "MONTE_CARLO_RUL")
        gamma = 9.17 if sub == "MONTE_CARLO_RUL" else (6.33 if sub == "ROTOR_FFT_HARMONICS" else 0.42)
        res["gateway_metadata"] = {
            "route": "serverless" if mode == "burst" else "k8s",
            "routing_reason": "DEFLECTED_SERVERLESS_HIGH_GAMMA" if mode == "burst" else "BASELINE_K8S_NORMAL",
            "gamma_ratio": gamma,
            "dynamic_threshold_pct": 78.5,
            "load_velocity_pct_per_s": 5.8 if mode == "burst" else 0.2,
            "composite_utilization_pct": round(cpu, 1),
            "active_compute_slots": 8 if mode == "burst" else 2,
            "max_base_compute_slots": 10,
            "prewarm_state": "WARM_READY" if mode == "burst" else "IDLE",
            "aks_p95_latency_ms": 520.0,
        }
        res["route"] = res["gateway_metadata"]["route"]
        res["routing_reason"] = res["gateway_metadata"]["routing_reason"]
        res["gamma_ratio"] = gamma
        return res
    else:
        import httpx

        client = httpx.AsyncClient(timeout=15.0)
        url = f"{settings.GATEWAY_BASE_URL.rstrip('/')}/api/twin/compute"
        try:
            resp = await client.request(request.method, url, json=body_json, timeout=15.0)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except Exception:
            from backend.digital_twin import execute_digital_twin_workload

            res = execute_digital_twin_workload(body_json, "AKS_BASE_POD")
            return res
        finally:
            await client.aclose()


# --- Single-Service Static Asset Mounting (for Render) ---
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    logger.info("Mounting frontend build from %s", FRONTEND_DIST)
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = FRONTEND_DIST / full_path
        if file_path.is_file() and not full_path.startswith("api"):
            return FileResponse(file_path)
        index_file = FRONTEND_DIST / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        return {"detail": "Frontend assets not yet built. Please run npm run build in frontend directory."}
else:
    logger.info("Frontend dist directory %s not found (API only mode until frontend is built).", FRONTEND_DIST)
