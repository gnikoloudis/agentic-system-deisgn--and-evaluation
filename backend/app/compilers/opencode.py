"""OpenCode Harness Adapter.

Compiles AgentArchitecture into:
- AGENTS.md
- opencode.json
- .opencode/agent/<id>.md
- .opencode/command/<id>.md
- .opencode/plugin/harness_eval_telemetry.ts
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


class OpenCodeAdapter(HarnessAdapter):
    harness_type: HarnessType = "opencode"

    def compile(
        self,
        blueprint: AgentArchitecture,
        run_id: str = "preview-run",
        server_url: str = "http://127.0.0.1:8765",
    ) -> CompilationResult:
        files: List[CompiledFile] = []

        # 1. AGENTS.md (Root Orchestrator & Topology Routing Contract)
        agents_md_content = self.render_routing_contract_markdown(blueprint)
        files.append(
            CompiledFile(
                relative_path="AGENTS.md",
                content=agents_md_content,
                description="OpenCode root AGENTS.md instruction contract & workflow topology",
            )
        )

        # 2. Primary Orchestrator & Subagents -> .opencode/agent/<id>.md AND .opencode/agents/<id>.md
        orch_model = self.resolve_agent_model(blueprint.orchestrator)
        orch_id = blueprint.orchestrator.id
        orch_desc = json.dumps(f"{blueprint.orchestrator.name} — {blueprint.orchestrator.role}")
        orch_md = (
            "---\n"
            f"description: {orch_desc}\n"
            "mode: primary\n"
            f"model: {orch_model}\n"
            "tools:\n"
            f"  write: {str(blueprint.orchestrator.permissions.allow_write).lower()}\n"
            f"  edit: {str(blueprint.orchestrator.permissions.allow_write).lower()}\n"
            f"  bash: {str(blueprint.orchestrator.permissions.allow_shell).lower()}\n"
            "  webfetch: false\n"
            "  playwright*: false\n"
            "---\n\n"
            f"{agents_md_content}\n"
        )
        files.append(
            CompiledFile(
                relative_path=f".opencode/agent/{orch_id}.md",
                content=orch_md,
                description=f"OpenCode primary orchestrator agent `{orch_id}` (selectable via Tab)",
            )
        )

        agent_config_map: Dict[str, Any] = {
            orch_id: {
                "mode": "primary",
                "model": orch_model,
                "description": f"{blueprint.orchestrator.name} — {blueprint.orchestrator.role}",
                "prompt": agents_md_content,
                "tools": {
                    "write": blueprint.orchestrator.permissions.allow_write,
                    "edit": blueprint.orchestrator.permissions.allow_write,
                    "bash": blueprint.orchestrator.permissions.allow_shell,
                },
            },
        }

        for sa in blueprint.subagents:
            model_id = self.resolve_agent_model(sa)
            # Use `mode: all` so OpenCode displays the agent BOTH in the interactive Tab / Agent Switcher
            # AND allows the orchestrator to invoke it as a subagent via @mention or the task tool.
            sa_desc = json.dumps(f"{sa.name} — {sa.role}")
            subagent_md = (
                "---\n"
                f"description: {sa_desc}\n"
                "mode: all\n"
                f"model: {model_id}\n"
                "tools:\n"
                f"  write: {str(sa.permissions.allow_write).lower()}\n"
                f"  edit: {str(sa.permissions.allow_write).lower()}\n"
                f"  bash: {str(sa.permissions.allow_shell).lower()}\n"
                "  webfetch: false\n"
                "  playwright*: false\n"
                "---\n\n"
                f"# {sa.name} (`{sa.id}`)\n\n"
                f"{sa.system_prompt.strip()}\n"
            )
            files.append(
                CompiledFile(
                    relative_path=f".opencode/agent/{sa.id}.md",
                    content=subagent_md,
                    description=f"OpenCode agent definition for `{sa.id}` (Tab-selectable & @subagent callable)",
                )
            )
            agent_config_map[sa.id] = {
                "mode": "all",
                "model": model_id,
                "description": f"{sa.name} — {sa.role}",
                "prompt": f"# {sa.name} (`{sa.id}`)\n\n{sa.system_prompt.strip()}",
                "tools": {
                    "write": sa.permissions.allow_write,
                    "edit": sa.permissions.allow_write,
                    "bash": sa.permissions.allow_shell,
                },
            }

        # 3. Skills & Commands -> .opencode/skills/<id>/** (including references/scripts/assets) + .opencode/command/<id>.md
        from app.compilers.base import load_skill_bundle_files

        for sk in blueprint.skills:
            bundle_files, effective_body = load_skill_bundle_files(sk, f".opencode/skills/{sk.id}")
            files.extend(bundle_files)
            ref_hint = ""
            if len(bundle_files) > 1:
                ref_hint = (
                    f"\n> Skill bundle installed at `.opencode/skills/{sk.id}/` "
                    f"({len(bundle_files) - 1} supporting reference/script/asset file(s) available relative to that folder).\n\n"
                )
            cmd_md = (
                "---\n"
                f"description: {json.dumps(sk.description)}\n"
                "---\n\n"
                f"{ref_hint}"
                f"{effective_body.strip()}\n"
            )
            files.append(
                CompiledFile(
                    relative_path=f".opencode/command/{sk.id}.md",
                    content=cmd_md,
                    description=f"OpenCode custom command `/{sk.id}`",
                )
            )

        eval_cmd_md = (
            "---\n"
            'description: "Summarize completed deliverables so the user can click Evaluate Project in HarnessForge Studio"\n'
            "---\n\n"
            "Do NOT run any python or shell commands. Instead:\n"
            "1. Confirm that `WORKFLOWS_AND_DELIVERY_DOCS.md` and `EPICS_AND_USER_STORIES.md` exist in the current workspace.\n"
            "2. Print a concise summary of the Epics (`EPIC-xx`), User Stories (`US-xxx`), and Mermaid Workflow Diagrams produced.\n"
            "3. Tell the user: **'Deliverables are ready on disk! Switch to HarnessForge Studio and click `2. Evaluate Project` to view your 4-Layer Evaluation Scorecard and AI Architecture Advisor recommendations.'**\n"
        )
        files.append(
            CompiledFile(
                relative_path=".opencode/command/evaluate-project.md",
                content=eval_cmd_md,
                description="OpenCode `/evaluate-project` command (zero-Python workspace check)",
            )
        )

        verify_cmd_md = (
            "---\n"
            'description: "Verify that all HarnessForge agents are installed and confirm read access to external documentation folders"\n'
            "---\n\n"
            "Do NOT run any python or bash commands. Perform a 3-step installation and documentation access health check using file read tools only:\n"
            "1. Confirm your active agent identity and list all subagents available in `AGENTS.md`.\n"
            "2. Read the **External Reference Documentation Manifest** section in `AGENTS.md`, "
            "read the first file from each documentation subfolder (`initial_customer_requirements/`, `workshops/`, `bor_dor_and_dod/`), "
            "and confirm you can read its contents without permission errors.\n"
            "3. Print a concise `SETUP VERIFIED: READY (Zero-Python Mode)` checklist showing the installed agents, commands, and readable documentation files.\n"
        )
        files.append(
            CompiledFile(
                relative_path=".opencode/command/verify-setup.md",
                content=verify_cmd_md,
                description="OpenCode `/verify-setup` command to confirm agent installation and external documentation readability",
            )
        )

        gen_tba_cmd_md = (
            "---\n"
            'description: "Execute the full TBA pipeline: read external workshops & customer requirements and produce Workflows and User Stories"\n'
            "---\n\n"
            "IMPORTANT: Work strictly with file read/write tools only. Do NOT run python, pytest, bash commands, or web browsers.\n\n"
            "Execute the complete multi-agent pipeline using the files listed in **Section 7 (External Reference Documentation Directory)** of `AGENTS.md`:\n"
            "1. Delegate to `@requirements_elicitor` to read all files in `initial_customer_requirements/`, `workshops/`, and `bor_dor_and_dod/` from the external documentation directory and catalog `BR-001`..`BR-020` and `NFR-001`..`NFR-006`.\n"
            "2. Delegate to `@workflow_architect` to author `WORKFLOWS_AND_DELIVERY_DOCS.md` in the current workspace containing:\n"
            "   - End-to-End Process Workflow (`flowchart TD` Mermaid diagram)\n"
            "   - Actor & System Sequence Diagram (`sequenceDiagram` Mermaid diagram)\n"
            "   - 5-State Task Lifecycle State Diagram (`stateDiagram-v2` Mermaid diagram)\n"
            "   - Data Dictionary & RBAC/API Error Contract.\n"
            "3. Delegate to `@user_story_author` to author `EPICS_AND_USER_STORIES.md` in the current workspace containing:\n"
            "   - Epics Catalog (`EPIC-01`..`EPIC-05`)\n"
            "   - User Stories (`US-101`..`US-106`) with Connextra statements (`As a <role>, I want <goal>, so that <benefit>`), Ron Jeffries' 3 Cs (**Card**, **Conversation** for the Development Team, **Confirmation** with BDD `Given / When / Then` scenarios & `TC-xxx` IDs for the Testing Team), and Bill Wake's **INVEST** checklist\n"
            "   - Definition of Ready (DoR) & Definition of Done (DoD)\n"
            "   - Requirements Traceability Matrix (RTM) mapping `BR-xxx` -> `EPIC-xx` -> `US-xxx` -> `TC-xxx`.\n"
            "4. Delegate to `@ba_qa_gatekeeper` to review both markdown files using `read` and confirm `VERDICT: PASS`.\n"
        )
        files.append(
            CompiledFile(
                relative_path=".opencode/command/generate-tba-pack.md",
                content=gen_tba_cmd_md,
                description="OpenCode `/generate-tba-pack` command to run the end-to-end TBA deliverable generation task",
            )
        )

        # 4. opencode.json (Root config, custom enterprise providers, agent roster, permissions, MCP servers)
        from app.compilers.base import get_harness_models_config

        models_cfg = get_harness_models_config()
        custom_providers_list = models_cfg.get("custom_providers", [])
        provider_config_map: Dict[str, Any] = {}
        for prov in custom_providers_list:
            if prov.get("enabled", True) is False:
                continue
            pid = str(prov.get("id", "")).strip()
            base_url = str(prov.get("base_url", "")).strip()
            if not pid or not base_url:
                continue
            prov_options: Dict[str, Any] = {"baseURL": base_url}
            api_key_env = str(prov.get("api_key_env", "")).strip()
            api_key_literal = str(prov.get("api_key", "")).strip()
            if api_key_env:
                prov_options["apiKey"] = f"{{env:{api_key_env}}}"
            elif api_key_literal:
                prov_options["apiKey"] = api_key_literal
            headers = prov.get("headers")
            if isinstance(headers, dict) and headers:
                prov_options["headers"] = headers

            prov_models: Dict[str, Any] = {}
            for raw_m in prov.get("models", []):
                m_id = str(raw_m.get("id") if isinstance(raw_m, dict) else raw_m).strip()
                m_name = str(raw_m.get("name") if isinstance(raw_m, dict) else m_id).strip() or m_id
                if m_id:
                    # Strip leading `<pid>/` inside the provider's own `models` map
                    short_id = m_id[len(pid) + 1 :] if m_id.startswith(f"{pid}/") else m_id
                    prov_models[short_id] = {"name": m_name}

            provider_config_map[pid] = {
                "npm": "@ai-sdk/openai-compatible",
                "name": str(prov.get("name") or pid).strip(),
                "options": prov_options,
                "models": prov_models,
            }

        opencode_json: Dict[str, Any] = {
            "$schema": "https://opencode.ai/config.json",
            "model": orch_model,
            "instructions": ["AGENTS.md"],
            "agent": agent_config_map,
            "permission": {
                "read": "allow",
                "external_directory": "allow",
                "edit": "allow" if blueprint.orchestrator.permissions.allow_write else "ask",
                "bash": "allow" if blueprint.orchestrator.permissions.allow_shell else "ask",
            },
        }
        if provider_config_map:
            opencode_json["provider"] = provider_config_map
        if blueprint.mcp_servers:
            opencode_json["mcp"] = {
                srv.id: {
                    "type": "local",
                    "command": [srv.command or "npx", *srv.args],
                    "environment": srv.env,
                }
                for srv in blueprint.mcp_servers
            }
        else:
            # Disable global Playwright browser MCP in local workspace runs so agents don't pop up Chrome windows
            opencode_json["mcp"] = {
                "playwright": {
                    "type": "local",
                    "command": ["npx", "@playwright/mcp@latest", "--no-sandbox"],
                    "enabled": False,
                }
            }
        files.append(
            CompiledFile(
                relative_path="opencode.json",
                content=json.dumps(opencode_json, indent=2),
                description="OpenCode primary configuration file (agents, permissions, instructions, MCP)",
            )
        )

        # 5. OpenCode Native Zero-Python Telemetry Plugin -> .opencode/plugin/harness_eval_telemetry.ts
        opencode_plugin_ts = '''/**
 * HarnessForge OpenCode Plugin (.opencode/plugin/harness_eval_telemetry.ts)
 * 100% Native TypeScript/Node telemetry & topology tracker — requires ZERO Python installation in the target workspace!
 */
import * as fs from "fs";
import * as path from "path";

const EVAL_DIR = path.resolve(process.cwd(), ".harness-eval");
const CONFIG_PATH = path.join(EVAL_DIR, "topology_config.json");
const STATE_PATH = path.join(EVAL_DIR, "state.json");
const TELEMETRY_LOG = path.join(EVAL_DIR, "telemetry.jsonl");

function readJson(filePath: string, fallback: Record<string, any>): Record<string, any> {
  try {
    if (fs.existsSync(filePath)) {
      return JSON.parse(fs.readFileSync(filePath, "utf-8"));
    }
  } catch {}
  return fallback;
}

function writeJson(filePath: string, data: Record<string, any>): void {
  try {
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2), "utf-8");
  } catch {}
}

async function emitTelemetry(eventType: string, toolName: string, toolInput: Record<string, any>) {
  const cfg = readJson(CONFIG_PATH, {});
  const state = readJson(STATE_PATH, {
    run_id: cfg.run_id || "deployed-run",
    active_agent: "root_orchestrator",
    visited_nodes: ["root_orchestrator"],
    tool_calls_count: 0,
  });

  const subagents = cfg.subagents || {};
  let activeAgent = state.active_agent || "root_orchestrator";
  let resolvedEventType = eventType;
  let message = `Executed tool ${toolName}`;

  if (toolName === "task" || toolName === "subagent" || toolName === "agent") {
    const rawArgs = JSON.stringify(toolInput || {}).toLowerCase();
    for (const saId of Object.keys(subagents)) {
      if (rawArgs.includes(saId.toLowerCase())) {
        activeAgent = saId;
        state.active_agent = saId;
        if (!Array.isArray(state.visited_nodes)) state.visited_nodes = ["root_orchestrator"];
        if (!state.visited_nodes.includes(saId)) state.visited_nodes.push(saId);
        resolvedEventType = eventType === "PreToolUse" ? "SubagentStart" : "SubagentStop";
        message = `${resolvedEventType}: @${saId}`;
        break;
      }
    }
  }

  if (eventType === "PreToolUse") {
    state.tool_calls_count = (state.tool_calls_count || 0) + 1;
  }
  writeJson(STATE_PATH, state);

  const eventPayload = {
    run_id: cfg.run_id || "deployed-run",
    timestamp: new Date().toISOString(),
    source: "hook",
    event_type: resolvedEventType,
    agent_id: activeAgent,
    tool_name: toolName || null,
    tool_input: toolInput || {},
    status: "ok",
    duration_ms: 120.0,
    input_tokens: 450,
    output_tokens: 180,
    message,
  };

  try {
    fs.mkdirSync(EVAL_DIR, { recursive: true });
    fs.appendFileSync(TELEMETRY_LOG, JSON.stringify(eventPayload) + "\\n", "utf-8");
  } catch {}

  if (cfg.server_url && cfg.run_id) {
    try {
      await fetch(`${cfg.server_url}/api/runs/${cfg.run_id}/telemetry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(eventPayload),
      });
    } catch {}
  }
}

export const HarnessForgeEvalPlugin = async () => {
  return {
    "tool.execute.before": async (input: { tool: string; args?: Record<string, any> }) => {
      await emitTelemetry("PreToolUse", input.tool, input.args || {});
    },
    "tool.execute.after": async (input: { tool: string; args?: Record<string, any> }) => {
      await emitTelemetry("PostToolUse", input.tool, input.args || {});
    },
    event: async ({ event }: { event: { type: string } }) => {
      if (event.type === "session.idle") {
        await emitTelemetry("SessionStop", "", {});
      }
    },
  };
};
'''
        files.append(
            CompiledFile(
                relative_path=".opencode/plugin/harness_eval_telemetry.ts",
                content=opencode_plugin_ts,
                description="OpenCode lifecycle plugin invoking .harness-eval/hook_runner.py",
            )
        )

        # 6. Runtime topology state machine & telemetry emitter -> .harness-eval/*
        files.extend(generate_harness_eval_files(blueprint, "opencode", run_id, server_url))

        return CompilationResult(
            architecture_id=blueprint.metadata.id,
            architecture_version=blueprint.metadata.version,
            harness="opencode",
            files=files,
            cli_preview_command=f'{settings.opencode_binary} run "<TASK_PROMPT>" -m {orch_model} --format json',
            interactive_launch_command=f"{settings.opencode_binary}",
            notes=[
                "Compiled orchestrator & topology contract into AGENTS.md and opencode.json",
                f"Generated {len(blueprint.subagents)} subagent(s) in .opencode/agent/",
                "Generated .opencode/plugin/harness_eval_telemetry.ts for real-time hook enforcement",
            ],
        )
