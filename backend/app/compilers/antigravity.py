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

        # Build explicit Antigravity Subagent Registration & Invocation Contract
        subagent_specs_lines: List[str] = [
            "",
            "## Antigravity Subagent Registration & Invocation Contract",
            "When executing this architecture in Antigravity (`agy` CLI or Antigravity IDE):",
            "1. Register any custom subagent below at the start of the task using `define_subagent` (if not already registered in this conversation).",
            "2. Delegate each stage in strict topology order using `invoke_subagent(TypeName=<Subagent ID>, Role=<Role>, Prompt=<Task>, Model=<Model Enum>)`.",
            "3. Work strictly offline using local files only (do NOT launch a browser or run python/pytest commands unless explicitly required).",
            "",
        ]
        for sa in blueprint.subagents:
            resolved_m = self.resolve_agent_model(sa)
            agy_enum = self._to_agy_subagent_model_enum(resolved_m, sa.model)
            subagent_specs_lines.extend(
                [
                    f"### Subagent `{sa.id}` — {sa.name}",
                    f"- **`define_subagent` Parameters**:",
                    f"  - `Name`: `\"{sa.id}\"`",
                    f"  - `Description`: {json.dumps(sa.role)}",
                    f"  - `EnableWriteTools`: `{str(sa.permissions.allow_write).lower()}`",
                    f"  - `EnableMCPTools`: `false`",
                    f"- **`invoke_subagent` Model**: `\"{agy_enum}\"` (Configured Model: `{resolved_m}`)",
                    f"- **`SystemPrompt`**:",
                    "```markdown",
                    sa.system_prompt.strip(),
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
            subagent_md = (
                "---\n"
                f"name: {sa.id}\n"
                f"description: {sa_desc}\n"
                f"model: {model_tier}\n"
                f"enable_write_tools: {str(sa.permissions.allow_write).lower()}\n"
                "enable_mcp_tools: false\n"
                "---\n\n"
                f"# {sa.name} (`{sa.id}`)\n\n"
                f"{sa.system_prompt.strip()}\n"
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

        # 3. Skills -> .agents/skills/<id>/SKILL.md and .agent/skills/<id>/SKILL.md
        all_skills: List[Dict[str, str]] = [
            {
                "id": sk.id,
                "name": sk.name,
                "description": sk.description,
                "instructions": sk.instructions,
            }
            for sk in blueprint.skills
        ]
        all_skills.extend(
            [
                {
                    "id": "verify-setup",
                    "name": "Verify Antigravity Agent Architecture & External Documentation Access",
                    "description": "Use this skill when the user asks to verify setup, check installed subagents, or confirm external documentation readability.",
                    "instructions": (
                        "Perform a 3-step installation and documentation access health check using file read tools only:\n"
                        "1. Confirm the active architecture in `GEMINI.md` and list all configured subagents.\n"
                        "2. Read the **External Reference Documentation Directory** section in `GEMINI.md`, "
                        "read the first file from each documentation subfolder (`initial_customer_requirements/`, `workshops/`, `bor_dor_and_dod/`), "
                        "and confirm its contents are readable.\n"
                        "3. Print a `SETUP VERIFIED: READY (Antigravity Mode)` checklist showing the active orchestrator, subagents, skills, and readable documentation files."
                    ),
                },
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
                {
                    "id": "evaluate-project",
                    "name": "Prepare Workspace Deliverables for HarnessForge Evaluation",
                    "description": "Use this skill when the user asks to evaluate the project or run /evaluate-project.",
                    "instructions": (
                        "1. Confirm that `WORKFLOWS_AND_DELIVERY_DOCS.md` and `EPICS_AND_USER_STORIES.md` exist in the current workspace.\n"
                        "2. Summarize the Epics, User Stories, and Mermaid Workflow Diagrams produced.\n"
                        "3. Inform the user: **'Deliverables are ready on disk! Switch to HarnessForge Studio and click `2. Evaluate Project` to view your 4-Layer Evaluation Scorecard and AI Architecture Advisor recommendations.'**"
                    ),
                },
            ]
        )

        for sk_dict in all_skills:
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

        # 5. MCP Servers -> .agents/mcp_config.json and .agent/mcp.json
        if blueprint.mcp_servers:
            mcp_payload = {
                "mcpServers": {
                    srv.id: {
                        "command": srv.command,
                        "args": srv.args,
                        "env": srv.env,
                    }
                    for srv in blueprint.mcp_servers
                }
            }
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
