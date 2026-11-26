"""Compiler registry and dispatch helpers for Claude Code, Antigravity, and OpenCode."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Dict, Optional

from app.compilers.antigravity import AntigravityAdapter
from app.compilers.base import HarnessAdapter
from app.compilers.claude_code import ClaudeCodeAdapter
from app.compilers.opencode import OpenCodeAdapter
from app.schemas.blueprint import AgentArchitecture, CompilationResult, HarnessType


_ADAPTERS: Dict[HarnessType, HarnessAdapter] = {
    "claude_code": ClaudeCodeAdapter(),
    "antigravity": AntigravityAdapter(),
    "opencode": OpenCodeAdapter(),
}


def get_adapter(harness: HarnessType) -> HarnessAdapter:
    if harness not in _ADAPTERS:
        raise ValueError(f"Unsupported harness type: {harness}")
    return _ADAPTERS[harness]


def compile_architecture(
    blueprint: AgentArchitecture,
    harness: HarnessType,
    run_id: str = "preview-run",
    server_url: str = "http://127.0.0.1:8765",
    workspace_dir: Optional[str] = None,
) -> CompilationResult:
    adapter = get_adapter(harness)
    return adapter.compile(
        blueprint,
        run_id=run_id,
        server_url=server_url,
        workspace_dir=workspace_dir,
    )


def deploy_compiled_files(compilation: CompilationResult, workspace_dir: Path) -> None:
    """Write all compiled harness files into the target workspace directory, cleaning stale agent/command dirs first."""
    workspace_dir.mkdir(parents=True, exist_ok=True)
    # Remove stale subagent/command definitions from any previously exported blueprint in this folder
    for stale_rel in (
        ".opencode/agent",
        ".opencode/agents",
        ".opencode/command",
        ".claude/agents",
        ".claude/commands",
        ".agent/agents",
        ".agents/agents",
    ):
        stale_dir = workspace_dir / stale_rel
        if stale_dir.exists() and stale_dir.is_dir():
            shutil.rmtree(stale_dir, ignore_errors=True)

    for compiled_file in compilation.files:
        dest = workspace_dir / compiled_file.relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(compiled_file.content, encoding="utf-8")
