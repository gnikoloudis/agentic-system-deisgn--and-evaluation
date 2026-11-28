"""Harness compilers package. Provides adapter factories and compilation orchestrator."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Dict, Type

from app.compilers.antigravity import AntigravityAdapter
from app.compilers.base import HarnessAdapter
from app.compilers.claude_code import ClaudeCodeAdapter
from app.compilers.opencode import OpenCodeAdapter
from app.schemas.blueprint import AgentArchitecture, CompilationResult, HarnessType

_ADAPTERS: Dict[HarnessType, Type[HarnessAdapter]] = {
    "claude_code": ClaudeCodeAdapter,
    "antigravity": AntigravityAdapter,
    "opencode": OpenCodeAdapter,
}


def get_adapter(harness: HarnessType) -> HarnessAdapter:
    adapter_cls = _ADAPTERS.get(harness)
    if not adapter_cls:
        raise ValueError(f"Unsupported harness: {harness}. Supported: {list(_ADAPTERS.keys())}")
    return adapter_cls()


def compile_architecture(
    blueprint: AgentArchitecture,
    harness: HarnessType,
    run_id: str = "preview-run",
    server_url: str = "http://127.0.0.1:8765",
    workspace_dir: str | None = None,
) -> CompilationResult:
    adapter = get_adapter(harness)
    return adapter.compile(
        blueprint=blueprint,
        run_id=run_id,
        server_url=server_url,
        workspace_dir=workspace_dir,
    )


def deploy_compiled_files(compilation: CompilationResult, workspace_dir: Path) -> None:
    """Write all compiled harness files into the target workspace directory with clean sweep of stale dirs."""
    workspace_dir.mkdir(parents=True, exist_ok=True)

    if compilation.harness == "antigravity":
        # Clean purge legacy and conflicting directories
        for stale_path in (
            workspace_dir / ".agent",
            workspace_dir / ".agents" / "agents",
            workspace_dir / ".agents" / "rules",
            workspace_dir / ".agents" / "skills",
            workspace_dir / ".agents" / "hooks.json",
            workspace_dir / ".agents" / "mcp_config.json",
            workspace_dir / ".agents" / ".harness-eval",
            workspace_dir / "mcp.json",
        ):
            if stale_path.is_dir():
                shutil.rmtree(stale_path, ignore_errors=True)
            elif stale_path.is_file():
                stale_path.unlink(missing_ok=True)
    elif compilation.harness == "claude_code":
        for stale_rel in (".claude/agents", ".claude/commands", ".agent"):
            stale_dir = workspace_dir / stale_rel
            if stale_dir.exists() and stale_dir.is_dir():
                shutil.rmtree(stale_dir, ignore_errors=True)
    elif compilation.harness == "opencode":
        for stale_rel in (
            ".opencode/agent",
            ".opencode/agents",
            ".opencode/command",
            ".agent",
        ):
            stale_dir = workspace_dir / stale_rel
            if stale_dir.exists() and stale_dir.is_dir():
                shutil.rmtree(stale_dir, ignore_errors=True)

    for compiled_file in compilation.files:
        dest = workspace_dir / compiled_file.relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(compiled_file.content, encoding="utf-8")
