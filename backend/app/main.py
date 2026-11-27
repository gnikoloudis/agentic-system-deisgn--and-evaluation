"""FastAPI application entrypoint for HarnessForge."""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.blueprints import router as blueprints_router
from app.api.evaluations import router as evaluations_router
from app.api.runs import router as runs_router
from app.api.tasks import router as tasks_router
from app.config import (
    AppUserConfig,
    ensure_directories,
    get_app_config,
    reset_app_token_pricing,
    save_app_config,
)
from app.db.database import cleanup_orphaned_running_runs, init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_directories()
    init_db()
    cleanup_orphaned_running_runs()
    yield


app = FastAPI(
    title="HarnessForge — Agent Architecture Design & Harness Evaluation Studio",
    version="0.1.0",
    description=(
        "Design multi-agent architectures visually or in YAML, compile to Claude Code, Antigravity, "
        "and OpenCode, execute tasks in isolated Git sandboxes, and evaluate performance across 4 layers."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(blueprints_router)
app.include_router(tasks_router)
app.include_router(runs_router)
app.include_router(evaluations_router)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "harnessforge",
        "supported_harnesses": ["claude_code", "antigravity", "opencode"],
    }


@app.get("/api/config", response_model=AppUserConfig)
def api_get_app_config() -> AppUserConfig:
    """Return persisted application configuration (target harness, harness lock, and per-provider token pricing)."""
    return get_app_config()


@app.put("/api/config", response_model=AppUserConfig)
def api_update_app_config(cfg: AppUserConfig) -> AppUserConfig:
    """Update persisted application configuration."""
    return save_app_config(cfg)


@app.post("/api/config/reset-pricing", response_model=AppUserConfig)
def api_reset_token_pricing() -> AppUserConfig:
    """Reset per-provider token pricing back to built-in defaults."""
    return reset_app_token_pricing()
