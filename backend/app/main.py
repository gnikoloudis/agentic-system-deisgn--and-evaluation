"""FastAPI application entrypoint for HarnessForge."""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.blueprints import router as blueprints_router
from app.api.evaluations import router as evaluations_router
from app.api.runs import router as runs_router
from app.api.tasks import router as tasks_router
from app.config import ensure_directories
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
