"""Global configuration and settings for HarnessForge."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BLUEPRINTS_DIR = ROOT_DIR / "blueprints"
TASKS_DIR = ROOT_DIR / "tasks"
SAMPLE_REPOS_DIR = TASKS_DIR / "sample_repos"
WORKSPACES_DIR = ROOT_DIR / ".harness-workspaces"
DATA_DIR = ROOT_DIR / ".harness-data"
DB_PATH = DATA_DIR / "harnessforge.db"


class JudgeProviderConfig(BaseModel):
    """Configuration for LLM-as-a-Judge and AI Architecture Advisor."""

    mode: Literal["harness_cli", "api_key", "heuristic_fallback"] = Field(
        default="harness_cli",
        description="Whether to use an installed harness CLI (claude/opencode/agy) or direct LLM API key.",
    )
    harness_cli: Literal["claude_code", "opencode", "antigravity"] = Field(
        default="claude_code",
        description="Which harness CLI to invoke when mode == 'harness_cli'.",
    )
    api_provider: Literal["anthropic", "openai", "gemini", "openrouter", "ollama"] = Field(
        default="anthropic",
        description="Which direct API provider to call when mode == 'api_key'.",
    )
    model: str = Field(
        default="claude-3-7-sonnet-latest",
        description="Model identifier for API or CLI invocation.",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Optional API key override (falls back to environment variables).",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Optional custom endpoint (e.g. Ollama http://localhost:11434/v1 or OpenRouter).",
    )


class AppSettings(BaseModel):
    """Runtime settings for HarnessForge server and CLI."""

    host: str = "127.0.0.1"
    port: int = 8765
    claude_binary: str = os.environ.get("CLAUDE_BINARY", "claude")
    opencode_binary: str = os.environ.get("OPENCODE_BINARY", "opencode")
    antigravity_binary: str = os.environ.get("AGY_BINARY", "agy")
    judge: JudgeProviderConfig = Field(default_factory=JudgeProviderConfig)


def ensure_directories() -> None:
    """Ensure required project directories exist."""
    for directory in (BLUEPRINTS_DIR, TASKS_DIR, SAMPLE_REPOS_DIR, WORKSPACES_DIR, DATA_DIR):
        directory.mkdir(parents=True, exist_ok=True)


settings = AppSettings()
