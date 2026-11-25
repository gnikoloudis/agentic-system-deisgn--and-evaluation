"""Claude Code Harness Adapter.

Compiles AgentArchitecture into:
- CLAUDE.md
- .claude/agents/<id>.md
- .claude/skills/<id>/SKILL.md
- .claude/commands/<id>.md
- .claude/settings.local.json
- .mcp.json
- .harness-eval/*
"""

from __future__ import annotations

import json
from typing import Dict, List

from app.compilers.base import HarnessAdapter
from app.compilers.hook_templates import generate_harness_eval_files
from app.config import settings
from app.schemas.blueprint import AgentArchitecture, CompilationResult, CompiledFile, HarnessType


CLAUDE_TOOL_NAME_MAP: Dict[str, str] = {
    "read": "Read",
    "write": "Write",
    "edit": "Edit",
    "grep": "Grep",
    "glob": "Glob",
    "bash": "Bash",
    "subagent": "Task",
}


class ClaudeCodeAdapter(HarnessAdapter):
    harness_type: HarnessType = "claude_code"

    def _map_tools(self, tools: List[str], allow_write: bool, allow_shell: bool) -> List[str]:
        mapped: List[str] = []
        for t in tools:
            canonical = CLAUDE_TOOL_NAME_MAP.get(t.lower(), t)
            if canonical in ("Write", "Edit", "MultiEdit") and not allow_write:
                continue
            if canonical == "Bash" and not allow_shell:
                continue
            if canonical not in mapped:
                mapped.append(canonical)
        return mapped

    def compile(
        self,
        blueprint: AgentArchitecture,
        run_id: str = "preview-run",
        server_url: str = "http://127.0.0.1:8765",
    ) -> CompilationResult:
        files: List[CompiledFile] = []

        # 1. CLAUDE.md (Root Orchestrator & Topology Routing Contract)
        claude_md_content = self.render_routing_contract_markdown(blueprint)
        files.append(
            CompiledFile(
                relative_path="CLAUDE.md",
                content=claude_md_content,
                description="Claude Code root project memory & multi-agent topology routing contract",
            )
        )

        # 2. Subagents -> .claude/agents/<id>.md
        from app.compilers.base import (
            load_skill_bundle_files,
            render_agent_runtime_constraints_markdown,
            resolve_effective_skill_slug,
        )

        blueprint.normalize_topology_edges()
        for sa in blueprint.subagents:
            sa_tools = self._map_tools(sa.tools, sa.permissions.allow_write, sa.permissions.allow_shell)
            for mcp_id in sa.mcp_servers:
                mcp_tool_glob = f"mcp__{mcp_id}__*"
                if mcp_tool_glob not in sa_tools:
                    sa_tools.append(mcp_tool_glob)
            tools_str = ", ".join(sa_tools)
            model_id = self.resolve_agent_model(sa)
            sa_skills = blueprint.skills_for_agent(sa.id)
            sa_constraints_md = render_agent_runtime_constraints_markdown(sa, sa_skills, model_id)
            subagent_md = (
                "---\n"
                f"name: {sa.id}\n"
                f"description: {sa.role}\n"
                f"tools: {tools_str}\n"
                f"model: {model_id}\n"
                f"max_turns: {sa.max_turns}\n"
                "---\n\n"
                f"# {sa.name} (`{sa.id}`)\n\n"
                f"{sa.system_prompt.strip()}\n"
                f"{sa_constraints_md}"
            )
            files.append(
                CompiledFile(
                    relative_path=f".claude/agents/{sa.id}.md",
                    content=subagent_md,
                    description=f"Claude Code native subagent definition for `{sa.id}`",
                )
            )

        # 3. Skills & Slash Commands -> .claude/skills/<slug>/** (including references/scripts/assets) and .claude/commands/<slug>.md

        for sk in blueprint.skills:
            slug = resolve_effective_skill_slug(sk)
            bundle_files, effective_body = load_skill_bundle_files(sk, f".claude/skills/{slug}")
            files.extend(bundle_files)
            files.append(
                CompiledFile(
                    relative_path=f".claude/commands/{slug}.md",
                    content=f"{effective_body.strip()}\n",
                    description=f"Claude Code slash command `/{slug}`",
                )
            )

        # 3b. Explicit Custom User Commands -> .claude/commands/<cmd.id>.md
        import re as _re

        for cmd in blueprint.commands:
            c_slug = _re.sub(r"[^a-z0-9_-]+", "-", cmd.id.strip().lstrip("/").lower()).strip("-") or "custom-cmd"
            cmd_content = (
                "---\n"
                f"description: {json.dumps(cmd.description)}\n"
                "---\n\n"
                f"{cmd.prompt.strip()}\n"
            )
            files.append(
                CompiledFile(
                    relative_path=f".claude/commands/{c_slug}.md",
                    content=cmd_content,
                    description=f"Claude Code user-defined slash command `/{c_slug}`",
                )
            )

        # 4. Hooks & Permissions -> .claude/settings.local.json (derived from blueprint canvas permissions)
        allow_rules: List[str] = []
        deny_rules: List[str] = []

        def _add_unique(lst: List[str], item: str) -> None:
            if item and item not in lst:
                lst.append(item)

        for t in self._map_tools(
            blueprint.orchestrator.tools,
            blueprint.orchestrator.permissions.allow_write,
            blueprint.orchestrator.permissions.allow_shell,
        ):
            if t != "Bash":
                _add_unique(allow_rules, t)
        for sa in blueprint.subagents:
            for t in self._map_tools(sa.tools, sa.permissions.allow_write, sa.permissions.allow_shell):
                if t != "Bash":
                    _add_unique(allow_rules, t)

        all_agents = [blueprint.orchestrator, *blueprint.subagents]
        any_shell = any(ag.permissions.allow_shell for ag in all_agents)
        custom_allowed_cmds = [c for ag in all_agents for c in ag.permissions.allowed_commands if c.strip()]
        if custom_allowed_cmds:
            for cmd in custom_allowed_cmds:
                _add_unique(allow_rules, f"Bash({cmd}*)")
        elif any_shell:
            for default_cmd in ("pytest", "python", "git status", "git diff"):
                _add_unique(allow_rules, f"Bash({default_cmd}*)")

        for srv in blueprint.mcp_servers:
            _add_unique(allow_rules, f"mcp__{srv.id}__*")

        for ag in all_agents:
            for blocked in ag.permissions.blocked_commands:
                if blocked.strip():
                    _add_unique(deny_rules, f"Bash({blocked.strip()}*)")

        settings_payload = {
            "permissions": {
                "allow": allow_rules,
                "deny": deny_rules,
            },
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python .harness-eval/hook_runner.py PreToolUse",
                            }
                        ],
                    }
                ],
                "PostToolUse": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python .harness-eval/hook_runner.py PostToolUse",
                            }
                        ],
                    }
                ],
                "SubagentStop": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python .harness-eval/hook_runner.py SubagentStop",
                            }
                        ],
                    }
                ],
                "Stop": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python .harness-eval/hook_runner.py Stop",
                            }
                        ],
                    }
                ],
            },
        }
        files.append(
            CompiledFile(
                relative_path=".claude/settings.local.json",
                content=json.dumps(settings_payload, indent=2),
                description="Claude Code permissions & lifecycle telemetry/guardrail hooks",
            )
        )

        # 5. MCP Servers -> .mcp.json (supports stdio, sse, and http transports)
        if blueprint.mcp_servers:
            mcp_servers_map: Dict[str, Any] = {}
            for srv in blueprint.mcp_servers:
                if srv.transport in ("sse", "http") and srv.url:
                    entry: Dict[str, Any] = {"type": srv.transport, "url": srv.url}
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
                    relative_path=".mcp.json",
                    content=json.dumps(mcp_payload, indent=2),
                    description="Claude Code project MCP server bindings",
                )
            )

        # 6. Runtime topology state machine & telemetry emitter -> .harness-eval/*
        files.extend(generate_harness_eval_files(blueprint, "claude_code", run_id, server_url))

        orch_model = self.resolve_agent_model(blueprint.orchestrator)
        return CompilationResult(
            architecture_id=blueprint.metadata.id,
            architecture_version=blueprint.metadata.version,
            harness="claude_code",
            files=files,
            cli_preview_command=(
                f'{settings.claude_binary} -p "<TASK_PROMPT>" --model {orch_model} '
                f"--output-format stream-json --verbose --max-turns {blueprint.orchestrator.budgets.max_turns}"
            ),
            interactive_launch_command=f"{settings.claude_binary}",
            notes=[
                "Compiled root orchestrator and topology matrix into CLAUDE.md",
                f"Generated {len(blueprint.subagents)} subagent(s) under .claude/agents/",
                "Injected dual-mode PreToolUse/PostToolUse/SubagentStop/Stop hooks in .claude/settings.local.json",
            ],
        )
