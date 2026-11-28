"""Antigravity (AGY) Harness Adapter.

Compiles AgentArchitecture into official Antigravity pure plugin architecture:
- GEMINI.md (Workspace-root always-on directory rule pointing to the active plugin)
- .agents/plugins/<architecture_id>/
  - plugin.json (Native Antigravity plugin manifest)
  - mcp_config.json (Official Antigravity MCP servers configuration)
  - hooks.json (Official Antigravity lifecycle telemetry & topology guard hooks)
  - rules/AGENTS.md (Consolidated architecture rules & subagent routing contract)
  - agents/<id>.md (Subagent specifications with YAML frontmatter)
  - skills/<id>/SKILL.md (All blueprint and built-in workflow skills)
- .harness-eval/* (Telemetry and topology state machine)
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from app.compilers.base import HarnessAdapter
from app.compilers.hook_templates import generate_harness_eval_files
from app.config import settings
from app.schemas.blueprint import AgentArchitecture, CompilationResult, CompiledFile, HarnessType


class AntigravityAdapter(HarnessAdapter):
    harness_type: HarnessType = "antigravity"

    def _to_agy_subagent_model_enum(self, resolved_model: str, raw_tier: str) -> str:
        """Map a model tier or ID to Antigravity's invoke_subagent Model enum ('inherit', 'flash_lite', 'flash', 'pro')."""
        m = (resolved_model or raw_tier or "").lower()
        if "flash" in m or "fast" in m or "low" in m:
            return "flash"
        if "neon" in m or "opus" in m or "reasoning" in m or "pro" in m or "high" in m:
            return "pro"
        return "inherit"

    def compile(
        self,
        blueprint: AgentArchitecture,
        run_id: str = "preview-run",
        server_url: str = "http://127.0.0.1:8765",
        workspace_dir: Optional[str] = None,
    ) -> CompilationResult:
        files: List[CompiledFile] = []

        from app.compilers.base import (
            is_tba_architecture,
            load_skill_bundle_files,
            render_agent_runtime_constraints_markdown,
            resolve_effective_skill_slug,
            resolve_mcp_args,
        )

        blueprint.normalize_topology_edges()
        arch_id = blueprint.metadata.id
        plugin_prefix = f".agents/plugins/{arch_id}"

        any_shell_allowed = blueprint.orchestrator.permissions.allow_shell or any(
            sa.permissions.allow_shell for sa in blueprint.subagents
        )
        shell_guidance = (
            "3. Respect each agent's configured `allow_write`, `allow_shell`, `allowed_commands`, and `blocked_commands` constraints below."
            if any_shell_allowed
            else "3. Work strictly offline using local files only (do NOT launch a browser or run shell commands unless explicitly authorized)."
        )

        # Build explicit Antigravity Subagent Registration & Invocation Contract
        subagent_specs_lines: List[str] = [
            "",
            "## Antigravity Subagent Registration & Invocation Contract",
            "When executing this architecture in Antigravity (`agy` CLI or Antigravity IDE):",
            "1. Register any custom subagent below at the start of the task using `define_subagent` (if not already registered in this conversation).",
            "2. Delegate each stage in strict topology order using `invoke_subagent(TypeName=<Subagent ID>, Role=<Role>, Prompt=<Task>, Model=<Model Enum>)`.",
            shell_guidance,
            "",
        ]
        for sa in blueprint.subagents:
            resolved_m = self.resolve_agent_model(sa)
            agy_enum = self._to_agy_subagent_model_enum(resolved_m, sa.model)
            sa_skills = blueprint.skills_for_agent(sa.id)
            sa_constraints_md = render_agent_runtime_constraints_markdown(sa, sa_skills, resolved_m)
            enable_write_or_shell = sa.permissions.allow_write or sa.permissions.allow_shell
            subagent_specs_lines.extend(
                [
                    f"### Subagent `{sa.id}` — {sa.name}",
                    "- **`define_subagent` Parameters**:",
                    f"  - `Name`: `\"{sa.id}\"`",
                    f"  - `Description`: {json.dumps(sa.role)}",
                    f"  - `EnableWriteTools`: `{str(enable_write_or_shell).lower()}` (Write: `{sa.permissions.allow_write}`, Shell: `{sa.permissions.allow_shell}`)",
                    f"  - `EnableMCPTools`: `{str(len(sa.mcp_servers) > 0).lower()}`"
                    + (
                        f" (Assigned MCP Servers: {', '.join(f'`{m}`' for m in sa.mcp_servers)})"
                        if sa.mcp_servers
                        else ""
                    ),
                    f"- **`invoke_subagent` Model**: `\"{agy_enum}\"` (Configured Model: `{resolved_m}`, Max Turns: `{sa.max_turns}`)",
                    "- **`SystemPrompt`**:",
                    "```markdown",
                    sa.system_prompt.strip(),
                    sa_constraints_md.strip(),
                    "```",
                    "",
                ]
            )

        agy_contract_body = self.render_routing_contract_markdown(blueprint) + "\n" + "\n".join(subagent_specs_lines)

        # 1. Root GEMINI.md (Official workspace-root always-on directory rule)
        root_gemini_content = (
            f"# Architecture: {blueprint.metadata.name} (v{blueprint.metadata.version})\n\n"
            f"> **Active Antigravity Plugin**: `{plugin_prefix}/`\n"
            f"> **Plugin Manifest**: [`plugin.json`]({plugin_prefix}/plugin.json)\n\n"
            f"{agy_contract_body}"
        )
        files.append(
            CompiledFile(
                relative_path="GEMINI.md",
                content=root_gemini_content,
                description="Antigravity workspace-root GEMINI.md rule (always active for directory scope)",
            )
        )

        # 2. Native Plugin Manifest (plugin.json)
        plugin_manifest = {
            "name": arch_id,
            "version": blueprint.metadata.version or "1.0.0",
            "description": blueprint.metadata.description or f"HarnessForge agentic system plugin for {blueprint.metadata.name}",
            "author": "HarnessForge",
        }
        files.append(
            CompiledFile(
                relative_path=f"{plugin_prefix}/plugin.json",
                content=json.dumps(plugin_manifest, indent=2),
                description=f"Antigravity native plugin manifest for `{arch_id}`",
            )
        )

        # 3. Consolidated Plugin Rules (rules/AGENTS.md)
        files.append(
            CompiledFile(
                relative_path=f"{plugin_prefix}/rules/AGENTS.md",
                content=agy_contract_body,
                description=f"Antigravity plugin consolidated rules for `{arch_id}`",
            )
        )

        # 4. Subagents -> .agents/plugins/<arch_id>/agents/<id>.md
        for sa in blueprint.subagents:
            model_tier = self.resolve_agent_model(sa)
            sa_desc = json.dumps(f"{sa.name} — {sa.role}")
            enable_mcp = len(sa.mcp_servers) > 0
            sa_skills = blueprint.skills_for_agent(sa.id)
            sa_constraints_md = render_agent_runtime_constraints_markdown(sa, sa_skills, model_tier)
            tools_str = ", ".join(sa.tools)
            subagent_md = (
                "---\n"
                f"name: {sa.id}\n"
                f"description: {sa_desc}\n"
                f"model: {model_tier}\n"
                f"tools: {tools_str}\n"
                f"max_turns: {sa.max_turns}\n"
                f"enable_write_tools: {str(sa.permissions.allow_write).lower()}\n"
                f"allow_shell: {str(sa.permissions.allow_shell).lower()}\n"
                f"allow_network: {str(sa.permissions.allow_network).lower()}\n"
                f"enable_mcp_tools: {str(enable_mcp).lower()}\n"
                "---\n\n"
                f"# {sa.name} (`{sa.id}`)\n\n"
                f"{sa.system_prompt.strip()}\n"
                f"{sa_constraints_md}"
            )
            files.append(
                CompiledFile(
                    relative_path=f"{plugin_prefix}/agents/{sa.id}.md",
                    content=subagent_md,
                    description=f"Antigravity subagent definition for `{sa.id}` in plugin agents/",
                )
            )

        # 5. Blueprint Skills -> .agents/plugins/<arch_id>/skills/<slug>/**
        for sk in blueprint.skills:
            slug = resolve_effective_skill_slug(sk)
            bundle_files, _ = load_skill_bundle_files(sk, f"{plugin_prefix}/skills/{slug}")
            files.extend(bundle_files)

        # 5b. Explicit Custom User Commands -> .agents/plugins/<arch_id>/skills/<cmd.id>/SKILL.md
        import re as _re

        for cmd in blueprint.commands:
            c_slug = _re.sub(r"[^a-z0-9_-]+", "-", cmd.id.strip().lstrip("/").lower()).strip("-") or "custom-cmd"
            agent_note = f"\n> Target Agent: `{cmd.agent}`\n" if cmd.agent else ""
            cmd_skill_md = (
                "---\n"
                f"name: {c_slug}\n"
                f"description: {json.dumps(cmd.description)}\n"
                "---\n\n"
                f"# Command: /{c_slug}\n{agent_note}\n"
                f"{cmd.prompt.strip()}\n"
            )
            files.append(
                CompiledFile(
                    relative_path=f"{plugin_prefix}/skills/{c_slug}/SKILL.md",
                    content=cmd_skill_md,
                    description=f"Antigravity plugin command skill `/{c_slug}`",
                )
            )

        subagent_list_str = (
            ", ".join(f"`{sa.id}`" for sa in blueprint.subagents) if blueprint.subagents else "*none (solo orchestrator)*"
        )
        skill_list_str = (
            ", ".join(f"`/{resolve_effective_skill_slug(sk)}`" for sk in blueprint.skills)
            if blueprint.skills
            else "*none*"
        )

        builtin_skills: List[Dict[str, str]] = [
            {
                "id": "verify-setup",
                "name": f"Verify Antigravity Setup — {blueprint.metadata.name}",
                "description": "Use this skill when the user asks to verify setup, check installed subagents, or confirm workspace configuration.",
                "instructions": (
                    "Perform a 3-step installation health check using file read tools:\n"
                    f"1. Confirm the active architecture `{blueprint.metadata.name}` (`{blueprint.metadata.id}`) in `GEMINI.md` and plugin manifest in `{plugin_prefix}/plugin.json`.\n"
                    f"2. Confirm the configured orchestrator (`{blueprint.orchestrator.id}`), subagents ({subagent_list_str}), and skills ({skill_list_str}).\n"
                    "3. If an **External Reference Documentation Directory** section exists in `GEMINI.md`, verify its files are readable, then print a `SETUP VERIFIED: READY (Antigravity Mode)` checklist."
                ),
            },
            {
                "id": "evaluate-project",
                "name": f"Prepare Workspace Deliverables for Evaluation — {blueprint.metadata.name}",
                "description": "Use this skill when the user asks to evaluate the project or run /evaluate-project.",
                "instructions": (
                    f"1. Summarize all deliverables and code/document changes produced by `{blueprint.orchestrator.id}` and subagents ({subagent_list_str}) in this workspace.\n"
                    "2. Confirm that all expected outputs and tests for the active benchmark task are present on disk.\n"
                    "3. Inform the user: **'Deliverables are ready on disk! Switch to HarnessForge Studio and click `2. Evaluate Project` to view your 4-Layer Evaluation Scorecard and AI Architecture Advisor recommendations.'**"
                ),
            },
        ]

        if is_tba_architecture(blueprint):
            builtin_skills.insert(
                1,
                {
                    "id": "generate-tba-pack",
                    "name": "Generate Full TBA Delivery Pack (Workflows + Epics & User Stories)",
                    "description": "Use this skill when the user asks to run the TBA pipeline, /generate-tba-pack, or produce WORKFLOWS_AND_DELIVERY_DOCS.md and EPICS_AND_USER_STORIES.md.",
                    "instructions": (
                        "Execute the complete multi-agent Technical Business Analyst pipeline using `GEMINI.md` and the external documentation directory:\n"
                        "1. Define and invoke `requirements_elicitor` to read all files in `initial_customer_requirements/`, `workshops/`, and `bor_dor_and_dod/` from the external documentation directory and catalog `BR-001`..`BR-020` and `NFR-001`..`NFR-006`.\n"
                        "2. Define and invoke `workflow_architect` to author `WORKFLOWS_AND_DELIVERY_DOCS.md` in the workspace root containing:\n"
                        "   - End-to-End Process Workflow (`flowchart TD` Mermaid diagram)\n"
                        "   - Actor & System Sequence Diagram (`sequenceDiagram` Mermaid diagram)\n"
                        "   - 5-State Task Lifecycle State Diagram (`stateDiagram-v2` Mermaid diagram)\n"
                        "   - Data Dictionary & RBAC/API Error Contract.\n"
                        "3. Define and invoke `user_story_author` to author `EPICS_AND_USER_STORIES.md` in the workspace root containing:\n"
                        "   - Epics Catalog (`EPIC-01`..`EPIC-05`)\n"
                        "   - User Stories (`US-101`..`US-106`) with Connextra statements (`As a <role>, I want <goal>, so that <benefit>`), Ron Jeffries' 3 Cs (**Card**, **Conversation** for the Development Team, **Confirmation** with BDD `Given / When / Then` scenarios & `TC-xxx` IDs for the Testing Team), and Bill Wake's **INVEST** checklist\n"
                        "   - Definition of Ready (DoR) & Definition of Done (DoD)\n"
                        "   - Requirements Traceability Matrix (RTM) mapping `BR-xxx` -> `EPIC-xx` -> `US-xxx` -> `TC-xxx`.\n"
                        "4. Define and invoke `ba_qa_gatekeeper` to review both markdown files and confirm `VERDICT: PASS`."
                    ),
                },
            )

        for sk_dict in builtin_skills:
            skill_md = (
                "---\n"
                f"name: {sk_dict['id']}\n"
                f"description: {json.dumps(sk_dict['description'])}\n"
                "---\n\n"
                f"# {sk_dict['name']}\n\n"
                f"{sk_dict['instructions'].strip()}\n"
            )
            files.append(
                CompiledFile(
                    relative_path=f"{plugin_prefix}/skills/{sk_dict['id']}/SKILL.md",
                    content=skill_md,
                    description=f"Antigravity plugin skill `{sk_dict['id']}`",
                )
            )

        # 6. Lifecycle Hooks -> .agents/plugins/<arch_id>/hooks.json
        py_exec = sys.executable.replace("\\", "/")
        official_hooks_json: Dict[str, Any] = {
            "harnessforge-telemetry": {
                "enabled": True,
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": f'"{py_exec}" .harness-eval/hook_runner.py PreToolUse',
                                "timeout": 5,
                            }
                        ],
                    }
                ],
                "PostToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": f'"{py_exec}" .harness-eval/hook_runner.py PostToolUse',
                                "timeout": 5,
                            }
                        ],
                    }
                ],
                "Stop": [
                    {
                        "type": "command",
                        "command": f'"{py_exec}" .harness-eval/hook_runner.py Stop',
                        "timeout": 5,
                    }
                ],
            }
        }
        files.append(
            CompiledFile(
                relative_path=f"{plugin_prefix}/hooks.json",
                content=json.dumps(official_hooks_json, indent=2),
                description=f"Antigravity plugin hooks.json for `{arch_id}`",
            )
        )

        # 7. MCP Servers -> .agents/plugins/<arch_id>/mcp_config.json (official Antigravity location)
        if blueprint.mcp_servers:
            mcp_servers_map: Dict[str, Any] = {}
            for srv in blueprint.mcp_servers:
                if srv.transport in ("sse", "http") and srv.url:
                    entry: Dict[str, Any] = {"url": srv.url}
                    if srv.env:
                        entry["env"] = srv.env
                    mcp_servers_map[srv.id] = entry
                else:
                    entry = {
                        "command": srv.command or "npx",
                        "args": resolve_mcp_args(srv.args, workspace_dir),
                    }
                    if srv.env:
                        entry["env"] = srv.env
                    mcp_servers_map[srv.id] = entry
            mcp_payload = {"mcpServers": mcp_servers_map}
            files.append(
                CompiledFile(
                    relative_path=f"{plugin_prefix}/mcp_config.json",
                    content=json.dumps(mcp_payload, indent=2),
                    description=f"Official Antigravity plugin MCP configuration for `{arch_id}`",
                )
            )

        # 8. Runtime topology state machine & telemetry emitter -> `.harness-eval/*` (workspace root)
        # AND `{plugin_prefix}/.harness-eval/*` so hook commands resolve regardless of CWD
        eval_files = generate_harness_eval_files(blueprint, "antigravity", run_id, server_url)
        files.extend(eval_files)
        for ef in eval_files:
            files.append(
                CompiledFile(
                    relative_path=f"{plugin_prefix}/{ef.relative_path}",
                    content=ef.content,
                    description=f"Plugin-local copy of {ef.relative_path}",
                )
            )

        orch_model = self.resolve_agent_model(blueprint.orchestrator)
        model_flag = f"--model {orch_model} " if orch_model not in ("inherit", "default", "pro", "flash") else ""
        return CompilationResult(
            architecture_id=blueprint.metadata.id,
            architecture_version=blueprint.metadata.version,
            harness="antigravity",
            files=files,
            cli_preview_command=(
                f'{settings.antigravity_binary} -p "<TASK_PROMPT>" {model_flag}'
                "--output-format stream-json --dangerously-skip-permissions"
            ),
            interactive_launch_command=f"{settings.antigravity_binary}",
            notes=[
                "Compiled always-on workspace rule & subagent orchestration contract into GEMINI.md",
                f"Generated {len(blueprint.subagents)} subagent definition(s) under {plugin_prefix}/agents/",
                f"Generated native plugin manifest in {plugin_prefix}/plugin.json + skills",
            ],
        )
