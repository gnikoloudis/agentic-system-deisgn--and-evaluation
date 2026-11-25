"""Antigravity (AGY) Harness Adapter.

Compiles AgentArchitecture into official Antigravity customization locations:
- GEMINI.md (Workspace-root always-on rule with routing contract & define_subagent / invoke_subagent specs)
- .agents/rules/orchestrator.md (and .agent/rules/orchestrator.md)
- .agents/agents/<id>.md (and .agent/agents/<id>.md)
- .agents/skills/<id>/SKILL.md (and .agent/skills/<id>/SKILL.md)
- .agents/hooks.json (Official Antigravity lifecycle hooks format)
- .agent/hooks/hooks.json
- .harness-eval/*
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

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
    ) -> CompilationResult:
        files: List[CompiledFile] = []

        from app.compilers.base import (
            is_tba_architecture,
            load_skill_bundle_files,
            render_agent_runtime_constraints_markdown,
            resolve_effective_skill_slug,
        )

        blueprint.normalize_topology_edges()
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

        # 1. GEMINI.md (Official workspace-root always-on rule, no frontmatter per rules.md spec)
        files.append(
            CompiledFile(
                relative_path="GEMINI.md",
                content=agy_contract_body,
                description="Antigravity workspace-root GEMINI.md rule (always active for directory scope)",
            )
        )

        # Also emit .agents/rules/orchestrator.md and .agent/rules/orchestrator.md for compatibility
        files.append(
            CompiledFile(
                relative_path=".agents/rules/orchestrator.md",
                content=agy_contract_body,
                description="Antigravity .agents/rules/orchestrator.md workspace rule",
            )
        )
        files.append(
            CompiledFile(
                relative_path=".agent/rules/orchestrator.md",
                content=agy_contract_body,
                description="Antigravity .agent/rules/orchestrator.md workspace rule",
            )
        )

        # 2. Subagents -> .agents/agents/<id>.md and .agent/agents/<id>.md
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
                    relative_path=f".agents/agents/{sa.id}.md",
                    content=subagent_md,
                    description=f"Antigravity subagent definition for `{sa.id}` in .agents/agents/",
                )
            )
            files.append(
                CompiledFile(
                    relative_path=f".agent/agents/{sa.id}.md",
                    content=subagent_md,
                    description=f"Antigravity subagent definition for `{sa.id}` in .agent/agents/",
                )
            )

        # 3. Skills -> .agents/skills/<slug>/** and .agent/skills/<slug>/** (supports folder-backed references/scripts/assets)

        for sk in blueprint.skills:
            slug = resolve_effective_skill_slug(sk)
            bundle_new, _ = load_skill_bundle_files(sk, f".agents/skills/{slug}")
            files.extend(bundle_new)
            bundle_legacy, _ = load_skill_bundle_files(sk, f".agent/skills/{slug}")
            files.extend(bundle_legacy)

        # 3b. Explicit Custom User Commands -> .agents/skills/<cmd.id>/SKILL.md
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
                    relative_path=f".agents/skills/{c_slug}/SKILL.md",
                    content=cmd_skill_md,
                    description=f"Antigravity user-defined command skill `/{c_slug}`",
                )
            )
            files.append(
                CompiledFile(
                    relative_path=f".agent/skills/{c_slug}/SKILL.md",
                    content=cmd_skill_md,
                    description=f"Antigravity user-defined command skill `/{c_slug}` (legacy path)",
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
                    f"1. Confirm the active architecture `{blueprint.metadata.name}` (`{blueprint.metadata.id}`) in `GEMINI.md`.\n"
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
                    relative_path=f".agents/skills/{sk_dict['id']}/SKILL.md",
                    content=skill_md,
                    description=f"Antigravity workspace skill `{sk_dict['id']}` in .agents/skills/",
                )
            )
            files.append(
                CompiledFile(
                    relative_path=f".agent/skills/{sk_dict['id']}/SKILL.md",
                    content=skill_md,
                    description=f"Antigravity workspace skill `{sk_dict['id']}` in .agent/skills/",
                )
            )

        # 4. Hooks -> Official .agents/hooks.json format
        # Note: Antigravity runs hook commands with CWD set to `.agents/` (or `.agent/hooks/` for legacy),
        # so we also emit `.agents/.harness-eval/` and use `../.harness-eval/hook_runner.py` or `.harness-eval/hook_runner.py` fallback.
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
                relative_path=".agents/hooks.json",
                content=json.dumps(official_hooks_json, indent=2),
                description="Official Antigravity .agents/hooks.json lifecycle telemetry & topology guard hooks",
            )
        )

        # 5. MCP Servers -> .agents/mcp_config.json and .agent/mcp.json (supports stdio, sse, http)
        if blueprint.mcp_servers:
            mcp_servers_map: Dict[str, Any] = {}
            for srv in blueprint.mcp_servers:
                if srv.transport in ("sse", "http") and srv.url:
                    entry: Dict[str, Any] = {"serverUrl": srv.url}
                    if srv.env:
                        entry["env"] = srv.env
                    mcp_servers_map[srv.id] = entry
                else:
                    mcp_servers_map[srv.id] = {
                        "command": srv.command or "npx",
                        "args": srv.args,
                        "env": srv.env,
                    }
            mcp_payload = {"mcpServers": mcp_servers_map}
            files.append(
                CompiledFile(
                    relative_path=".agents/mcp_config.json",
                    content=json.dumps(mcp_payload, indent=2),
                    description="Antigravity MCP server configuration",
                )
            )
            files.append(
                CompiledFile(
                    relative_path=".agent/mcp.json",
                    content=json.dumps(mcp_payload, indent=2),
                    description="Antigravity MCP server configuration",
                )
            )

        # 6. Runtime topology state machine & telemetry emitter -> both `.harness-eval/*` (workspace root)
        # AND `.agents/.harness-eval/*` (since Antigravity executes `.agents/hooks.json` with CWD = `.agents/`)
        eval_files = generate_harness_eval_files(blueprint, "antigravity", run_id, server_url)
        files.extend(eval_files)
        for ef in eval_files:
            files.append(
                CompiledFile(
                    relative_path=f".agents/{ef.relative_path}",
                    content=ef.content,
                    description=f"{ef.description} (in .agents/ working directory)",
                    executable=ef.executable,
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
                "Compiled always-on workspace rule & subagent orchestration contract into GEMINI.md and .agents/rules/orchestrator.md",
                f"Generated {len(blueprint.subagents)} subagent definition(s) in .agents/agents/",
                "Generated official .agents/hooks.json + skills (verify-setup, generate-tba-pack, evaluate-project)",
            ],
        )
