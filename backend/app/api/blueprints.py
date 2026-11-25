"""API endpoints for Architecture Blueprints (CRUD, Bidirectional YAML Sync, Multi-Harness Compile Preview, Direct Workspace Export)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.compilers import compile_architecture, deploy_compiled_files
from app.config import ROOT_DIR, settings
from app.db.database import save_run, utc_now_iso
from app.db.storage import (
    blueprint_to_yaml,
    delete_blueprint,
    get_blueprint,
    get_task,
    list_blueprints,
    list_tasks,
    save_blueprint,
    yaml_to_blueprint,
)
from app.schemas.blueprint import AgentArchitecture, CompilationResult, HarnessType
from app.schemas.evaluation import RunRecordSchema


router = APIRouter(prefix="/api/blueprints", tags=["blueprints"])


class BlueprintWithYamlResponse(BaseModel):
    blueprint: AgentArchitecture
    raw_yaml: str
    file_path: str


class SaveBlueprintRequest(BaseModel):
    blueprint: Optional[AgentArchitecture] = None
    raw_yaml: Optional[str] = None
    previous_id: Optional[str] = None


class ExportToDirectoryRequest(BaseModel):
    harness: HarnessType
    target_directory: str
    docs_directory: Optional[str] = None
    task_id: Optional[str] = None


@router.get("", response_model=List[AgentArchitecture])
def api_list_blueprints() -> List[AgentArchitecture]:
    return list_blueprints()


@router.get("/{architecture_id}", response_model=BlueprintWithYamlResponse)
def api_get_blueprint(architecture_id: str) -> BlueprintWithYamlResponse:
    found = get_blueprint(architecture_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Blueprint '{architecture_id}' not found")
    bp, raw_yaml, path = found
    return BlueprintWithYamlResponse(blueprint=bp, raw_yaml=raw_yaml, file_path=str(path))


@router.post("", response_model=BlueprintWithYamlResponse)
def api_save_blueprint(req: SaveBlueprintRequest) -> BlueprintWithYamlResponse:
    try:
        if req.raw_yaml:
            parsed = yaml_to_blueprint(req.raw_yaml)
            bp, yaml_str, path = save_blueprint(parsed, raw_yaml_override=req.raw_yaml)
        elif req.blueprint:
            bp, yaml_str, path = save_blueprint(req.blueprint)
        else:
            raise ValueError("Either 'blueprint' or 'raw_yaml' must be provided")
        if req.previous_id and req.previous_id != bp.metadata.id:
            delete_blueprint(req.previous_id)
        return BlueprintWithYamlResponse(blueprint=bp, raw_yaml=yaml_str, file_path=str(path))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid architecture blueprint: {exc}") from exc


class InspectSkillDirRequest(BaseModel):
    source_dir: str


@router.post("/inspect-skill-dir")
def api_inspect_skill_dir(req: InspectSkillDirRequest) -> Dict[str, Any]:
    """Inspect a local skill directory (SKILL.md + references/, scripts/, assets/, resources/) for one-click attachment."""
    from app.compilers.base import inspect_skill_directory

    try:
        return inspect_skill_directory(req.source_dir)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/convert-yaml", response_model=BlueprintWithYamlResponse)
def api_convert_yaml(req: SaveBlueprintRequest) -> BlueprintWithYamlResponse:
    """Two-way in-memory sync between structured JSON blueprint and raw YAML without writing to disk."""
    try:
        if req.raw_yaml:
            bp = yaml_to_blueprint(req.raw_yaml)
            return BlueprintWithYamlResponse(blueprint=bp, raw_yaml=req.raw_yaml, file_path="")
        if req.blueprint:
            raw_yaml = blueprint_to_yaml(req.blueprint)
            return BlueprintWithYamlResponse(blueprint=req.blueprint, raw_yaml=raw_yaml, file_path="")
        raise ValueError("Provide either blueprint or raw_yaml")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{architecture_id}")
def api_delete_blueprint(architecture_id: str) -> Dict[str, Any]:
    deleted = delete_blueprint(architecture_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Blueprint '{architecture_id}' not found")
    return {"deleted": True, "id": architecture_id}


class InlineCompilePreviewRequest(BaseModel):
    blueprint: AgentArchitecture
    harness: HarnessType


@router.post("/compile-preview", response_model=CompilationResult)
def api_compile_preview_inline(req: InlineCompilePreviewRequest) -> CompilationResult:
    """Compile an in-memory blueprint (including unsaved studio edits) into native harness files for live preview."""
    return compile_architecture(req.blueprint, harness=req.harness, run_id="preview-run")


@router.get("/{architecture_id}/compile/{harness}", response_model=CompilationResult)
def api_compile_preview(architecture_id: str, harness: HarnessType) -> CompilationResult:
    found = get_blueprint(architecture_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Blueprint '{architecture_id}' not found")
    bp, _, _ = found
    return compile_architecture(bp, harness=harness, run_id="preview-run")


@router.post("/{architecture_id}/export")
def api_export_to_directory(architecture_id: str, req: ExportToDirectoryRequest) -> Dict[str, Any]:
    """Compile and deploy the architecture directly into a target project directory and create a tracked RunRecord for live telemetry & evaluation."""
    found = get_blueprint(architecture_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Blueprint '{architecture_id}' not found")
    bp, _, _ = found

    raw_dir = req.target_directory.strip() or "."
    candidate = Path(raw_dir)
    target_path = candidate.resolve() if candidate.is_absolute() else (ROOT_DIR / candidate).resolve()

    # Resolve optional external documentation directory (only linked when explicitly specified)
    raw_docs = (req.docs_directory or "").strip()
    docs_path: Optional[Path] = None
    if raw_docs:
        docs_cand = Path(raw_docs)
        docs_path = (
            docs_cand.resolve() if docs_cand.is_absolute() else (ROOT_DIR / docs_cand).resolve()
        )

    discovered_docs: List[str] = []
    if docs_path and docs_path.exists():
        for doc_file in sorted(docs_path.rglob("*")):
            if doc_file.is_file() and doc_file.suffix.lower() in (".md", ".txt", ".json", ".csv", ".yaml"):
                if ".harness-eval" not in str(doc_file) and ".opencode" not in str(doc_file):
                    discovered_docs.append(str(doc_file.resolve()).replace("\\", "/"))

    # Determine best matching benchmark task for evaluating this project folder
    chosen_task_id = req.task_id
    if not chosen_task_id:
        if "test_application_docs" in str(target_path) or "technical-business-analyst" in architecture_id:
            chosen_task_id = "tba-focusflow-todo-app" if get_task("tba-focusflow-todo-app") else "tba-chargeback-dispute-system"
        elif "consulting" in architecture_id:
            chosen_task_id = "consulting-saas-turnaround"
        else:
            all_tasks = list_tasks()
            chosen_task_id = all_tasks[0].id if all_tasks else "bugfix-auth-token"

    task_tuple = get_task(chosen_task_id)
    task_name = task_tuple[0].name if task_tuple else chosen_task_id

    run_id = f"deploy-{uuid.uuid4().hex[:8]}"
    server_url = f"http://{settings.host}:{settings.port}"
    compilation = compile_architecture(bp, harness=req.harness, run_id=run_id, server_url=server_url)

    # Inject External Reference Documentation Manifest into root instruction files & subagent definitions
    # so agents deployed in ANY workspace folder know the exact absolute paths of the external docs.
    if docs_path and docs_path.exists() and discovered_docs:
        docs_root_posix = str(docs_path).replace("\\", "/")
        manifest_lines = [
            "",
            "---",
            "## 7. External Reference Documentation Directory (Authorized Read Access)",
            f"- **External Documentation Root Path**: `{docs_root_posix}`",
            "- **Access Rule**: All agents and subagents have `external_directory: allow` and `read: allow` permissions to read every file in this external folder.",
            "- **Discovered Reference Documents**:",
        ]
        for dp in discovered_docs[:40]:
            manifest_lines.append(f"  - `{dp}`")
        manifest_block = "\n".join(manifest_lines) + "\n"

        for cf in compilation.files:
            if cf.relative_path in (
                "AGENTS.md",
                "CLAUDE.md",
                "GEMINI.md",
                ".agent/rules/orchestrator.md",
                ".agents/rules/orchestrator.md",
            ) or cf.relative_path.startswith(
                (".opencode/agent/", ".claude/agents/", ".agent/agents/", ".agents/agents/")
            ):
                cf.content = cf.content.rstrip() + "\n" + manifest_block

    deploy_compiled_files(compilation, target_path)

    # Create a tracked interactive deployment RunRecord so live hook events from that folder stream to HarnessForge
    deployed_run = RunRecordSchema(
        id=run_id,
        architecture_id=bp.metadata.id,
        architecture_name=bp.metadata.name,
        architecture_version=bp.metadata.version,
        task_id=chosen_task_id,
        task_name=f"[Deployed Project: {target_path.name}] {task_name}",
        harness=req.harness,
        mode="interactive",
        status="waiting_for_user",
        sandbox_path=str(target_path),
        cli_command=compilation.interactive_launch_command,
        started_at=utc_now_iso(),
    )
    save_run(deployed_run, blueprint_snapshot=bp.model_dump(mode="json"))

    from app.compilers.base import is_tba_architecture, resolve_effective_skill_slug

    installed_commands = ["/verify-setup", "/evaluate-project"]
    if is_tba_architecture(bp):
        installed_commands.insert(1, "/generate-tba-pack")
    installed_commands.extend(f"/{cmd.id.lstrip('/')}" for cmd in bp.commands)
    installed_commands.extend(f"/{resolve_effective_skill_slug(sk)}" for sk in bp.skills)

    return {
        "exported": True,
        "run_id": run_id,
        "architecture_id": architecture_id,
        "harness": req.harness,
        "target_directory": str(target_path),
        "docs_directory": str(docs_path) if docs_path and docs_path.exists() else None,
        "discovered_docs": discovered_docs,
        "installed_agents": [bp.orchestrator.id, *[sa.id for sa in bp.subagents]],
        "installed_commands": installed_commands,
        "files_written": [f.relative_path for f in compilation.files],
        "launch_command": compilation.interactive_launch_command,
    }
