"""Git Worktree & Isolated Clone Sandbox Manager."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from app.compilers import deploy_compiled_files
from app.config import ROOT_DIR, WORKSPACES_DIR, ensure_directories
from app.schemas.blueprint import CompilationResult


HARNESS_GENERATED_EXCLUDES = [
    "CLAUDE.md",
    ".claude/",
    ".mcp.json",
    "GEMINI.md",
    ".agent/",
    ".agents/",
    "AGENTS.md",
    "opencode.json",
    ".opencode/",
    ".harness-eval/",
    "__pycache__/",
    ".pytest_cache/",
]


def _run_git(args: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def resolve_workspace_source(workspace_source: str) -> Path:
    candidate = Path(workspace_source)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    rel = (ROOT_DIR / workspace_source).resolve()
    if rel.exists():
        return rel
    raise FileNotFoundError(f"Workspace source not found: {workspace_source}")


def is_git_repo(path: Path) -> bool:
    res = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=path)
    return res.returncode == 0 and res.stdout.strip() == "true"


def create_isolated_sandbox(
    run_id: str,
    workspace_source: str,
    compilation: CompilationResult,
    base_commit: Optional[str] = None,
) -> Path:
    """Create a fresh isolated sandbox via git worktree (if source is a git repo) or git-initialized clone."""
    ensure_directories()
    source_path = resolve_workspace_source(workspace_source)
    sandbox_dir = (WORKSPACES_DIR / run_id).resolve()

    if sandbox_dir.exists():
        shutil.rmtree(sandbox_dir, ignore_errors=True)

    used_worktree = False
    if is_git_repo(source_path):
        target_ref = base_commit or "HEAD"
        wt_res = _run_git(["worktree", "add", "--detach", str(sandbox_dir), target_ref], cwd=source_path)
        if wt_res.returncode == 0 and sandbox_dir.exists():
            used_worktree = True

    if not used_worktree:
        shutil.copytree(source_path, sandbox_dir, dirs_exist_ok=True)
        _run_git(["init"], cwd=sandbox_dir)
        _run_git(["config", "user.email", "harnessforge@local.dev"], cwd=sandbox_dir)
        _run_git(["config", "user.name", "HarnessForge Sandbox"], cwd=sandbox_dir)
        _run_git(["add", "-A"], cwd=sandbox_dir)
        _run_git(["commit", "-m", "HarnessForge baseline snapshot"], cwd=sandbox_dir)

    # Configure git exclusions so compiled harness files do not pollute task diff evaluation
    git_dir_res = _run_git(["rev-parse", "--git-dir"], cwd=sandbox_dir)
    if git_dir_res.returncode == 0:
        git_dir = Path(git_dir_res.stdout.strip())
        if not git_dir.is_absolute():
            git_dir = (sandbox_dir / git_dir).resolve()
        info_exclude = git_dir / "info" / "exclude"
        info_exclude.parent.mkdir(parents=True, exist_ok=True)
        existing = info_exclude.read_text(encoding="utf-8") if info_exclude.exists() else ""
        extra_lines = "\n".join(HARNESS_GENERATED_EXCLUDES)
        info_exclude.write_text(existing.rstrip() + "\n" + extra_lines + "\n", encoding="utf-8")

    # Deploy compiled architecture files into the sandbox
    deploy_compiled_files(compilation, sandbox_dir)
    return sandbox_dir


def extract_sandbox_git_diff(sandbox_dir: Path) -> Tuple[str, List[str]]:
    """Extract unified git diff and list of changed task files (excluding injected harness configs)."""
    if not sandbox_dir.exists():
        return "", []

    # Stage untracked task files (exclude list filters out harness configs)
    _run_git(["add", "-N", "."], cwd=sandbox_dir)
    diff_res = _run_git(["diff", "HEAD"], cwd=sandbox_dir)
    name_res = _run_git(["diff", "--name-only", "HEAD"], cwd=sandbox_dir)

    excluded_prefixes = tuple(e.rstrip("/") for e in HARNESS_GENERATED_EXCLUDES)
    changed_files: List[str] = []
    for line in (name_res.stdout or "").splitlines():
        clean = line.strip().replace("\\", "/")
        if not clean:
            continue
        if any(clean == pref or clean.startswith(pref + "/") for pref in excluded_prefixes):
            continue
        changed_files.append(clean)

    return (diff_res.stdout or "").strip(), changed_files
