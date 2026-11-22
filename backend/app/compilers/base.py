"""Base HarnessAdapter, User-Configurable Per-Harness Model Registry, and Dual-Mode Prompt Routing Contract generator."""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Union
import yaml

from app.config import DATA_DIR, ROOT_DIR, ensure_directories, settings
from app.schemas.blueprint import (
    AgentArchitecture,
    CompilationResult,
    CompiledFile,
    HarnessType,
    OrchestratorSpec,
    SkillSpec,
    SubagentSpec,
)

HARNESS_MODELS_PATH = DATA_DIR / "harness_models.json"

DEFAULT_MODEL_TIER_MAP: Dict[HarnessType, Dict[str, str]] = {
    "claude_code": {
        "default": "claude-sonnet-4-20250514",
        "reasoning": "claude-opus-4-20250514",
        "coding": "claude-sonnet-4-20250514",
        "fast": "claude-3-5-haiku-latest",
    },
    "antigravity": {
        "default": "gemini-4-argon-medium",
        "reasoning": "gemini-4-neon-high",
        "coding": "gemini-4-argon-high",
        "fast": "gemini-3.8-flash-medium",
    },
    "opencode": {
        "default": "opencode/big-pickle",
        "reasoning": "opencode/nemotron-3.5-super-vl-free",
        "coding": "opencode/big-pickle",
        "fast": "opencode/deepseek-v4.1-flash-free",
    },
}

DEFAULT_NATIVE_MODELS: Dict[HarnessType, List[Dict[str, str]]] = {
    "claude_code": [
        {"id": "claude-sonnet-4-20250514", "label": "Claude Sonnet 4 (Balanced Coding & Orchestration)", "tier": "coding"},
        {"id": "claude-opus-4-20250514", "label": "Claude Opus 4 (Deep Architecture & Reasoning)", "tier": "reasoning"},
        {"id": "claude-3-7-sonnet-latest", "label": "Claude 3.7 Sonnet (Extended Thinking)", "tier": "coding"},
        {"id": "claude-3-5-haiku-latest", "label": "Claude 3.5 Haiku (Low-Latency QA & Verifier)", "tier": "fast"},
    ],
    "antigravity": [
        {"id": "gemini-4-argon-medium", "label": "Gemini 4 Argon (Medium) — Default Balanced", "tier": "default"},
        {"id": "gemini-4-argon-high", "label": "Gemini 4 Argon (High) — High-Precision Coding", "tier": "coding"},
        {"id": "gemini-4-argon-low", "label": "Gemini 4 Argon (Low) — Fast Execution", "tier": "fast"},
        {"id": "gemini-4-neon-high", "label": "Gemini 4 Neon (High) — Deep Reasoning & Planning", "tier": "reasoning"},
        {"id": "gemini-4-neon-xhigh", "label": "Gemini 4 Neon (XHigh) — Max Reasoning Effort", "tier": "reasoning"},
        {"id": "gemini-4-neon-medium", "label": "Gemini 4 Neon (Medium)", "tier": "coding"},
        {"id": "gemini-4-hydrogen-high", "label": "Gemini 4 Hydrogen (High)", "tier": "reasoning"},
        {"id": "gemini-4-hydrogen-medium", "label": "Gemini 4 Hydrogen (Medium)", "tier": "coding"},
        {"id": "gemini-pro-orchestrator-neon", "label": "Orchestrator (Neon) — Multi-Agent Coordinator", "tier": "default"},
        {"id": "gemini-pro-orchestrator-g1-pro", "label": "Orchestrator (Argon) — Multi-Agent Coordinator", "tier": "default"},
        {"id": "gemini-3.8-flash-high", "label": "Gemini 3.8 Flash (High) — Fast QA Verifier", "tier": "fast"},
        {"id": "gemini-3.8-flash-medium", "label": "Gemini 3.8 Flash (Medium) — Low-Cost Critic", "tier": "fast"},
        {"id": "gemini-3.8-flash-low", "label": "Gemini 3.8 Flash (Low)", "tier": "fast"},
        {"id": "claude-opus-5-5-high", "label": "Claude Opus 5.5 (High)", "tier": "reasoning"},
        {"id": "claude-opus-5-5-medium", "label": "Claude Opus 5.5 (Medium)", "tier": "reasoning"},
        {"id": "claude-sonnet-5-5-high", "label": "Claude Sonnet 5.5 (High)", "tier": "coding"},
        {"id": "claude-sonnet-5-5-medium", "label": "Claude Sonnet 5.5 (Medium)", "tier": "coding"},
        {"id": "gpt-oss-120b-medium", "label": "GPT-OSS 120B (Medium)", "tier": "coding"},
        {"id": "inherit", "label": "inherit (Use Parent Session Model)", "tier": "default"},
        {"id": "pro", "label": "pro (Antigravity Pro Subagent Tier)", "tier": "reasoning"},
        {"id": "flash", "label": "flash (Antigravity Flash Subagent Tier)", "tier": "fast"},
    ],
    "opencode": [
        {"id": "opencode/big-pickle", "label": "opencode/big-pickle (Primary Coding & Synthesis)", "tier": "coding"},
        {"id": "opencode/nemotron-3.5-super-vl-free", "label": "opencode/nemotron-3.5-super-vl-free (Deep Reasoning)", "tier": "reasoning"},
        {"id": "opencode/deepseek-v4.1-flash-free", "label": "opencode/deepseek-v4.1-flash-free (Fast QA & Verifier)", "tier": "fast"},
        {"id": "opencode/mimo-v2.6-flash-free", "label": "opencode/mimo-v2.6-flash-free (Fast Flash)", "tier": "fast"},
        {"id": "opencode/nemotron-3.5-lightning-free", "label": "opencode/nemotron-3.5-lightning-free (Low Latency)", "tier": "fast"},
        {"id": "opencode/beam-free", "label": "opencode/beam-free", "tier": "coding"},
        {"id": "opencode/flint-40b-free", "label": "opencode/flint-40b-free", "tier": "coding"},
        {"id": "opencode/hy4-flash-free", "label": "opencode/hy4-flash-free", "tier": "fast"},
        {"id": "opencode/iceman-free", "label": "opencode/iceman-free", "tier": "coding"},
        {"id": "opencode/longcat-2.5-free", "label": "opencode/longcat-2.5-free", "tier": "coding"},
        {"id": "opencode/tidepool-alpha-free", "label": "opencode/tidepool-alpha-free", "tier": "reasoning"},
    ],
}

MODEL_BEST_PRACTICES: Dict[str, str] = {
    "orchestrator": (
        "Best Practice (Orchestrator): Use a balanced instruction-following model (`default` / `Orchestrator` / `Sonnet` / `Argon Medium`). "
        "The root coordinator should focus on clean routing and delegation rather than burning heavy reasoning tokens."
    ),
    "reasoning": (
        "Best Practice (`reasoning` tier — Planners, BA Discovery & Security Auditors): Assign your highest-reasoning model "
        "(`Opus` / `Gemini 4 Neon High` / `Nemotron 3.5 Super`) to read-only discovery nodes that analyze complex requirements and edge cases."
    ),
    "coding": (
        "Best Practice (`coding` tier — Coders, Workflow Architects & Story Authors): Assign a high-throughput generation model "
        "(`Sonnet` / `Gemini 4 Argon High` / `opencode/big-pickle`) to nodes that author large code files or detailed specifications."
    ),
    "fast": (
        "Best Practice (`fast` tier — QA Verifiers & Gatekeepers): Assign a fast, low-cost model (`Haiku` / `Gemini 3.8 Flash` / `DeepSeek Flash`) "
        "to critic nodes that execute pytest and verify checklists—reducing multi-loop retry latency and cost by up to 65%."
    ),
}


def get_harness_models_config() -> Dict[str, Any]:
    """Load user-configurable per-harness model tier mappings, native model catalogs, and enterprise OpenAI-compatible providers."""
    ensure_directories()
    if HARNESS_MODELS_PATH.exists():
        try:
            data = json.loads(HARNESS_MODELS_PATH.read_text(encoding="utf-8"))
            if "tier_map" in data and "native_models" in data:
                data.setdefault("custom_providers", [])
                data["best_practices"] = MODEL_BEST_PRACTICES
                return data
        except Exception:
            pass
    default_payload = {
        "tier_map": DEFAULT_MODEL_TIER_MAP,
        "native_models": DEFAULT_NATIVE_MODELS,
        "custom_providers": [],
        "best_practices": MODEL_BEST_PRACTICES,
    }
    HARNESS_MODELS_PATH.write_text(json.dumps(default_payload, indent=2), encoding="utf-8")
    return default_payload


def save_harness_models_config(
    tier_map: Dict[str, Dict[str, str]],
    native_models: Dict[str, List[Dict[str, str]]],
    custom_providers: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Persist custom per-harness model tier mappings, model lists, and enterprise OpenAI-compatible providers."""
    ensure_directories()
    if custom_providers is None:
        existing = get_harness_models_config()
        custom_providers = existing.get("custom_providers", [])

    # Ensure every model listed in an enterprise provider is registered in native_models["opencode"]
    oc_list = list(native_models.get("opencode", []))
    existing_oc_ids = {m["id"] for m in oc_list}
    for prov in custom_providers:
        pid = str(prov.get("id", "")).strip()
        pname = str(prov.get("name") or pid).strip()
        if not pid:
            continue
        for raw_m in prov.get("models", []):
            m_id = str(raw_m.get("id") if isinstance(raw_m, dict) else raw_m).strip()
            m_name = str(raw_m.get("name") if isinstance(raw_m, dict) else m_id).strip() or m_id
            if not m_id:
                continue
            full_id = m_id if m_id.startswith(f"{pid}/") else f"{pid}/{m_id}"
            if full_id not in existing_oc_ids:
                oc_list.append(
                    {
                        "id": full_id,
                        "label": f"{pname}: {m_name} ({full_id})",
                        "tier": str(raw_m.get("tier", "coding")) if isinstance(raw_m, dict) else "coding",
                    }
                )
                existing_oc_ids.add(full_id)
    native_models["opencode"] = oc_list

    payload = {
        "tier_map": tier_map,
        "native_models": native_models,
        "custom_providers": custom_providers,
        "best_practices": MODEL_BEST_PRACTICES,
    }
    HARNESS_MODELS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def sync_models_from_installed_clis() -> Dict[str, Any]:
    """Query `agy models` and `opencode models` on the host machine to auto-discover available models."""
    cfg = get_harness_models_config()
    native = cfg["native_models"]

    # 1. Discover from `agy models`
    agy_bin = shutil.which(settings.antigravity_binary)
    if agy_bin:
        try:
            proc = subprocess.run([agy_bin, "models"], capture_output=True, text=True, timeout=8, encoding="utf-8")
            if proc.returncode == 0:
                existing_ids = {m["id"] for m in native.get("antigravity", [])}
                for line in proc.stdout.splitlines():
                    line = line.strip()
                    if not line or line.startswith("Fetching"):
                        continue
                    parts = line.split("\t")
                    m_id = parts[0].strip()
                    m_label = f"{parts[1].strip()} ({m_id})" if len(parts) > 1 else m_id
                    if m_id and m_id not in existing_ids:
                        tier_guess = "fast" if "flash" in m_id or "low" in m_id else ("reasoning" if "neon" in m_id or "opus" in m_id else "coding")
                        native.setdefault("antigravity", []).append({"id": m_id, "label": m_label, "tier": tier_guess})
                        existing_ids.add(m_id)
        except Exception:
            pass

    # 2. Discover from `opencode models`
    oc_bin = shutil.which(settings.opencode_binary)
    if oc_bin:
        try:
            proc = subprocess.run([oc_bin, "models"], capture_output=True, text=True, timeout=8, encoding="utf-8")
            if proc.returncode == 0:
                existing_ids = {m["id"] for m in native.get("opencode", [])}
                for line in proc.stdout.splitlines():
                    m_id = line.strip()
                    if m_id and "/" in m_id and m_id not in existing_ids:
                        tier_guess = "fast" if "flash" in m_id or "lightning" in m_id else "coding"
                        native.setdefault("opencode", []).append({"id": m_id, "label": m_id, "tier": tier_guess})
                        existing_ids.add(m_id)
        except Exception:
            pass

    return save_harness_models_config(cfg["tier_map"], native)


_IGNORED_SKILL_DIRS = {".git", "__pycache__", "node_modules", ".venv", ".pytest_cache"}


def _parse_skill_frontmatter(raw_md: str) -> tuple[Dict[str, Any], str]:
    """Extract YAML frontmatter (if present) and markdown body from a SKILL.md file."""
    m = re.match(r"^---\s*\r?\n([\s\S]*?)\r?\n---\s*\r?\n?([\s\S]*)$", raw_md)
    if not m:
        return {}, raw_md
    try:
        meta = yaml.safe_load(m.group(1)) or {}
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}
    return meta, m.group(2)


def resolve_skill_source_dir(source_dir: str) -> Optional[Path]:
    raw = (source_dir or "").strip()
    if not raw:
        return None
    cand = Path(raw)
    resolved = cand.resolve() if cand.is_absolute() else (ROOT_DIR / cand).resolve()
    return resolved if resolved.exists() and resolved.is_dir() else None


def inspect_skill_directory(source_dir: str) -> Dict[str, Any]:
    """Inspect a local skill folder containing SKILL.md + references/, scripts/, assets/, resources/."""
    resolved = resolve_skill_source_dir(source_dir)
    if not resolved:
        raise ValueError(f"Skill folder '{source_dir}' does not exist or is not a directory")

    skill_md_path = resolved / "SKILL.md"
    meta: Dict[str, Any] = {}
    body = ""
    if skill_md_path.exists():
        meta, body = _parse_skill_frontmatter(skill_md_path.read_text(encoding="utf-8", errors="replace"))

    discovered_files: List[str] = []
    counts = {"references": 0, "scripts": 0, "assets": 0, "resources": 0, "other": 0}
    for fpath in sorted(resolved.rglob("*")):
        if not fpath.is_file():
            continue
        rel_parts = fpath.relative_to(resolved).parts
        if any(p in _IGNORED_SKILL_DIRS for p in rel_parts):
            continue
        rel_posix = "/".join(rel_parts)
        discovered_files.append(rel_posix)
        if rel_posix.lower() == "skill.md":
            continue
        top = rel_parts[0].lower() if len(rel_parts) > 1 else "other"
        if top in counts:
            counts[top] += 1
        else:
            counts["other"] += 1

    skill_slug = str(meta.get("name") or resolved.name).strip().lower().replace(" ", "-")
    skill_title = str(meta.get("title") or meta.get("name") or resolved.name).replace("-", " ").title()
    skill_desc = str(meta.get("description") or f"Folder-backed skill loaded from {resolved.name}").strip()

    return {
        "source_dir": str(resolved).replace("\\", "/"),
        "has_skill_md": skill_md_path.exists(),
        "id": skill_slug,
        "name": skill_title,
        "description": skill_desc,
        "instructions_preview": body.strip()[:6000],
        "files": discovered_files,
        "counts": counts,
    }


def _sanitize_skill_slug(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", (raw or "").strip().lower()).strip("-")
    return slug or "custom-skill"


def resolve_effective_skill_slug(sk: SkillSpec) -> str:
    """Resolve the canonical directory/command slug for a skill.

    If `source_dir` is set and `sk.id` is still a generic placeholder (e.g. `ba-template-2` or
    `custom-skill-1`), automatically adopt the skill's real `name:` from `SKILL.md` frontmatter
    (or the folder name) so deployed directories and `SKILL.md` never drift out of sync.
    """
    current_slug = _sanitize_skill_slug(sk.id)
    is_placeholder = bool(re.match(r"^(ba-template|custom-skill|skill)[-_]?\d*$", current_slug))
    resolved = resolve_skill_source_dir(sk.source_dir or "")
    if resolved and is_placeholder:
        skill_md_path = resolved / "SKILL.md"
        if skill_md_path.exists():
            meta, _ = _parse_skill_frontmatter(skill_md_path.read_text(encoding="utf-8", errors="replace"))
            fm_name = str(meta.get("name") or "").strip()
            if fm_name:
                return _sanitize_skill_slug(fm_name)
        return _sanitize_skill_slug(resolved.name)
    return current_slug


def load_skill_bundle_files(sk: SkillSpec, target_skill_root: str) -> tuple[List[CompiledFile], str]:
    """Compile a SkillSpec into one or more CompiledFiles (including references/, scripts/, resources/, assets/ if source_dir is set)."""
    root = target_skill_root.rstrip("/")
    slug = resolve_effective_skill_slug(sk)
    resolved = resolve_skill_source_dir(sk.source_dir or "")
    compiled: List[CompiledFile] = []

    if resolved:
        has_skill_md = False
        effective_body = sk.instructions or ""
        for fpath in sorted(resolved.rglob("*")):
            if not fpath.is_file():
                continue
            rel_parts = fpath.relative_to(resolved).parts
            if any(p in _IGNORED_SKILL_DIRS for p in rel_parts):
                continue
            rel_posix = "/".join(rel_parts)
            try:
                text_content = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if rel_posix.lower() == "skill.md":
                has_skill_md = True
                _, parsed_body = _parse_skill_frontmatter(text_content)
                if parsed_body.strip():
                    effective_body = parsed_body
            is_exec = rel_parts[0].lower() == "scripts" or fpath.suffix.lower() in (".sh", ".py", ".ps1")
            compiled.append(
                CompiledFile(
                    relative_path=f"{root}/{rel_posix}",
                    content=text_content,
                    description=f"Bundled skill file `{rel_posix}` for skill `{slug}`",
                    executable=is_exec,
                )
            )
        if not has_skill_md:
            fallback_md = (
                "---\n"
                f"name: {slug}\n"
                f"description: {json.dumps(sk.description)}\n"
                "---\n\n"
                f"# {sk.name}\n\n"
                f"{effective_body.strip()}\n"
            )
            compiled.insert(
                0,
                CompiledFile(
                    relative_path=f"{root}/SKILL.md",
                    content=fallback_md,
                    description=f"Skill definition `SKILL.md` for `{slug}`",
                ),
            )
        return compiled, effective_body

    # Standard inline skill (single SKILL.md)
    skill_md = (
        "---\n"
        f"name: {slug}\n"
        f"description: {json.dumps(sk.description)}\n"
        "---\n\n"
        f"# {sk.name}\n\n"
        f"{sk.instructions.strip()}\n"
    )
    compiled.append(
        CompiledFile(
            relative_path=f"{root}/SKILL.md",
            content=skill_md,
            description=f"Skill definition for `{slug}`",
        )
    )
    return compiled, sk.instructions


class HarnessAdapter(ABC):
    """Abstract base compiler for translating an AgentArchitecture into native harness files."""

    harness_type: HarnessType

    def resolve_model(self, model_tier_or_id: str, harness_overrides: Optional[Dict[str, str]] = None) -> str:
        """Resolve an agent's model for this harness: checks explicit per-harness override first, then tier_map."""
        if harness_overrides and self.harness_type in harness_overrides and harness_overrides[self.harness_type].strip():
            return harness_overrides[self.harness_type].strip()
        cfg = get_harness_models_config()
        tier_map = cfg.get("tier_map", DEFAULT_MODEL_TIER_MAP).get(self.harness_type, {})
        return tier_map.get(model_tier_or_id, model_tier_or_id)

    def resolve_agent_model(self, agent_spec: Union[OrchestratorSpec, SubagentSpec]) -> str:
        return self.resolve_model(agent_spec.model, getattr(agent_spec, "harness_models", None))

    def render_routing_contract_markdown(self, bp: AgentArchitecture) -> str:
        """Compile the visual graph topology, subagent roster, permissions, and hooks into an explicit routing contract."""
        orch_resolved_model = self.resolve_agent_model(bp.orchestrator)
        lines: List[str] = [
            f"# Architecture Blueprint: {bp.metadata.name} (`{bp.metadata.id}` v{bp.metadata.version})",
            "",
            "## 1. Root Orchestrator Role & System Instructions",
            f"- **Target Harness**: `{self.harness_type}` | **Orchestrator Model**: `{orch_resolved_model}` (Tier: `{bp.orchestrator.model}`)",
            "",
            bp.orchestrator.system_prompt.strip(),
            "",
            "## 2. Execution Budgets & Constraints",
            f"- **Max Turns**: `{bp.orchestrator.budgets.max_turns}`",
            f"- **Max Budget (USD)**: `${bp.orchestrator.budgets.max_cost_usd:.2f}`",
            f"- **Timeout**: `{bp.orchestrator.budgets.timeout_seconds}s`",
            f"- **Orchestrator Direct File Write Allowed**: `{bp.orchestrator.permissions.allow_write}`",
            f"- **Orchestrator Direct Shell Execution Allowed**: `{bp.orchestrator.permissions.allow_shell}`",
            "",
        ]

        if bp.subagents:
            lines.append("## 3. Deployed Subagent Roster")
            lines.append("| Subagent ID | Name | Role | Resolved Model | Write Allowed | Shell Allowed |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for sa in bp.subagents:
                lines.append(
                    f"| `{sa.id}` | {sa.name} | {sa.role} | `{self.resolve_agent_model(sa)}` "
                    f"| `{sa.permissions.allow_write}` | `{sa.permissions.allow_shell}` |"
                )
            lines.append("")

        if bp.topology.edges:
            lines.append(
                f"## 4. Mandatory Workflow Topology (`{bp.topology.pattern}` — Enforcement: `{bp.topology.enforcement_mode}`)"
            )
            lines.append(
                "You MUST adhere to the following directed transition sequence when delegating across subagents and skills:"
            )
            sorted_edges = sorted(bp.topology.edges, key=lambda e: e.order)
            for edge in sorted_edges:
                req_badge = "REQUIRED" if edge.required else "CONDITIONAL"
                lines.append(
                    f"{edge.order}. **`{edge.source}` -> `{edge.target}`** [{req_badge}] "
                    f"— *Trigger*: {edge.condition} (Max loops: `{edge.max_loops}`)"
                )
            lines.append("")

        if bp.skills:
            lines.append("## 5. Available Skills & Workflows")
            for sk in bp.skills:
                cmd = f" (`{sk.trigger_command}`)" if sk.trigger_command else ""
                lines.append(f"- **`{sk.id}`**{cmd}: {sk.description}")
            lines.append("")

        if bp.hooks:
            lines.append("## 6. Active Runtime Guardrail Hooks")
            for hk in bp.hooks:
                lines.append(
                    f"- **`{hk.id}`** (`{hk.event}` matching `{hk.matcher}` on `{hk.target_agent}` -> `{hk.action}`): {hk.message}"
                )
            lines.append("")

        return "\n".join(lines)

    @abstractmethod
    def compile(
        self,
        blueprint: AgentArchitecture,
        run_id: str = "preview-run",
        server_url: str = "http://127.0.0.1:8765",
    ) -> CompilationResult:
        """Compile blueprint into target harness files and CLI invocation commands."""
        raise NotImplementedError
