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
