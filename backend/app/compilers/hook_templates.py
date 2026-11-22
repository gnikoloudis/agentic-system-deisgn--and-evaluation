"""Generator for .harness-eval/hook_runner.py and topology state-machine configuration."""

from __future__ import annotations

import json
from typing import List

from app.schemas.blueprint import AgentArchitecture, CompiledFile, HarnessType


def generate_harness_eval_files(
    blueprint: AgentArchitecture,
    harness: HarnessType,
    run_id: str,
    server_url: str = "http://127.0.0.1:8765",
) -> List[CompiledFile]:
    """Generate the injected .harness-eval/ runtime scripts for dual-mode topology enforcement and real-time telemetry."""

    subagent_map = {
        sa.id: {
            "name": sa.name,
            "allow_write": sa.permissions.allow_write,
            "allow_shell": sa.permissions.allow_shell,
            "allowed_commands": sa.permissions.allowed_commands,
            "blocked_commands": sa.permissions.blocked_commands,
        }
        for sa in blueprint.subagents
    }

    topology_config = {
        "run_id": run_id,
        "architecture_id": blueprint.metadata.id,
        "harness": harness,
        "server_url": server_url.rstrip("/"),
        "enforcement_mode": blueprint.topology.enforcement_mode,
        "entry_node": blueprint.topology.entry_node,
        "orchestrator": {
            "id": blueprint.orchestrator.id,
            "allow_write": blueprint.orchestrator.permissions.allow_write,
            "allow_shell": blueprint.orchestrator.permissions.allow_shell,
            "allowed_commands": blueprint.orchestrator.permissions.allowed_commands,
            "blocked_commands": blueprint.orchestrator.permissions.blocked_commands,
        },
        "subagents": subagent_map,
        "edges": [e.model_dump() for e in sorted(blueprint.topology.edges, key=lambda x: x.order)],
        "hooks": [h.model_dump() for h in blueprint.hooks],
    }

    initial_state = {
        "run_id": run_id,
        "active_agent": blueprint.orchestrator.id,
        "visited_nodes": [blueprint.orchestrator.id],
        "edge_counts": {},
        "tool_calls_count": 0,
        "violations_blocked": 0,
    }

    hook_runner_script = '''#!/usr/bin/env python3
"""HarnessForge Runtime Topology Enforcer & Telemetry Emitter (.harness-eval/hook_runner.py)."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
# If executed from inside `.agents/.harness-eval/`, also mirror state/telemetry to workspace root `.harness-eval/`
ROOT_EVAL_DIR = (
    EVAL_DIR.parent.parent / ".harness-eval"
    if EVAL_DIR.parent.name in (".agents", ".agent")
    else EVAL_DIR
)
CONFIG_PATH = EVAL_DIR / "topology_config.json"
STATE_PATH = ROOT_EVAL_DIR / "state.json" if ROOT_EVAL_DIR.exists() else EVAL_DIR / "state.json"
TELEMETRY_LOG = ROOT_EVAL_DIR / "telemetry.jsonl" if ROOT_EVAL_DIR.exists() else EVAL_DIR / "telemetry.jsonl"

WRITE_TOOL_PATTERNS = re.compile(r"^(Write|Edit|MultiEdit|CreateFile|write_file|edit_file|patch)$", re.IGNORECASE)
SHELL_TOOL_PATTERNS = re.compile(r"^(Bash|run_command|shell|terminal|exec)$", re.IGNORECASE)
SUBAGENT_TOOL_PATTERNS = re.compile(r"^(Task|Agent|invoke_subagent|subagent|dispatch_agent)$", re.IGNORECASE)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: dict) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def save_json(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if path != EVAL_DIR / "state.json" and EVAL_DIR.exists():
            (EVAL_DIR / "state.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def emit_telemetry(config: dict, event_payload: dict) -> None:
    """Append event to local JSONL and fire-and-forget POST to HarnessForge server."""
    try:
        TELEMETRY_LOG.parent.mkdir(parents=True, exist_ok=True)
        with TELEMETRY_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event_payload) + "\\n")
    except Exception:
        pass

    server_url = config.get("server_url")
    run_id = config.get("run_id")
    if not server_url or not run_id or run_id == "preview-run":
        return

    url = f"{server_url}/api/runs/{run_id}/telemetry"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(event_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.5):
            pass
    except Exception:
        pass


def detect_target_subagent(tool_name: str, tool_input: dict, subagents: dict) -> str | None:
    """Detect if a tool invocation is actually invoking/delegating to a subagent (not merely defining or reading it)."""
    t_lower = (tool_name or "").lower()
    if SUBAGENT_TOOL_PATTERNS.match(t_lower):
        for key in ("subagent_type", "agent", "name", "Name", "TypeName", "recipient", "target", "Role"):
            val = tool_input.get(key)
            if isinstance(val, str) and val in subagents:
                return val
        raw = json.dumps(tool_input).lower()
        for sa_id in subagents:
            if sa_id.lower() in raw:
                return sa_id
    return None


def estimate_tool_tokens(tool_name: str, tool_input: dict) -> tuple[int, int, float]:
    """Estimate input/output tokens and cost for hook-captured tool steps."""
    raw_len = len(json.dumps(tool_input))
    in_tok = max(320, min(4800, 350 + raw_len // 3))
    t_lower = (tool_name or "").lower()
    if t_lower in ("write_file", "edit_file", "write", "edit", "createfile"):
        out_tok = max(450, min(6500, 300 + raw_len // 4))
    elif t_lower in ("invoke_subagent", "task", "agent"):
        out_tok = 620
    else:
        out_tok = 210
    cost_usd = round((in_tok * 3.0 + out_tok * 15.0) / 1_000_000, 6)
    return in_tok, out_tok, cost_usd


def print_hook_stdout(is_antigravity: bool, hook_event: str, decision: str = "allow", reason: str = "") -> None:
    """Emit official Antigravity JSON stdout contract when running under Antigravity hooks.json."""
    if not is_antigravity:
        return
    if hook_event == "PreToolUse":
        payload = {"decision": decision}
        if reason:
            payload["reason"] = reason
        sys.stdout.write(json.dumps(payload) + "\\n")
        sys.stdout.flush()
    elif hook_event == "PostToolUse":
        sys.stdout.write("{}\\n")
        sys.stdout.flush()
    elif hook_event == "Stop":
        payload = {"decision": decision}
        if reason:
            payload["reason"] = reason
        sys.stdout.write(json.dumps(payload) + "\\n")
        sys.stdout.flush()


def main() -> int:
    hook_event = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("HARNESS_HOOK_EVENT", "PreToolUse")
    config = load_json(CONFIG_PATH, {})
    now_epoch = time.time()
    state = load_json(
        STATE_PATH,
        {
            "run_id": config.get("run_id", "unknown"),
            "active_agent": "root_orchestrator",
            "visited_nodes": ["root_orchestrator"],
            "edge_counts": {},
            "tool_calls_count": 0,
            "violations_blocked": 0,
            "last_event_epoch": now_epoch,
        },
    )

    stdin_data = {}
    if not sys.stdin.isatty():
        try:
            raw_in = sys.stdin.read().strip() if os.environ.get("HARNESS_READ_STDIN") != "0" else ""
            if raw_in:
                stdin_data = json.loads(raw_in)
        except Exception:
            stdin_data = {}

    is_antigravity = (
        config.get("harness") == "antigravity"
        or "toolCall" in stdin_data
        or "hookEventName" in stdin_data
        or "conversationId" in stdin_data
    )

    # Support both Claude Code (`tool_name`, `tool_input`) and Antigravity (`toolCall.name`, `toolCall.args`)
    tool_call_obj = stdin_data.get("toolCall") if isinstance(stdin_data.get("toolCall"), dict) else {}
    tool_name = (
        stdin_data.get("tool_name")
        or stdin_data.get("tool")
        or tool_call_obj.get("name")
        or os.environ.get("HARNESS_TOOL_NAME")
        or ""
    )
    tool_input = (
        stdin_data.get("tool_input")
        or stdin_data.get("input")
        or tool_call_obj.get("args")
        or {}
    )
    if not isinstance(tool_input, dict):
        tool_input = {"raw": str(tool_input)}

    if stdin_data.get("transcriptPath"):
        state["transcript_path"] = stdin_data["transcriptPath"]

    last_epoch = float(state.get("last_event_epoch") or now_epoch)
    elapsed_ms = round(max(120.0, min(45000.0, (now_epoch - last_epoch) * 1000.0)), 2)
    state["last_event_epoch"] = now_epoch

    active_agent = state.get("active_agent", "root_orchestrator")
    subagents = config.get("subagents", {})
    enforce = config.get("enforcement_mode", "dual") in ("hook", "dual")

    # Check if this tool call delegates to a subagent
    delegated_subagent = detect_target_subagent(tool_name, tool_input, subagents)
    if hook_event == "PreToolUse" and delegated_subagent:
        edges = config.get("edges", [])
        visited = set(state.get("visited_nodes", ["root_orchestrator"]))
        if enforce and edges and SUBAGENT_TOOL_PATTERNS.match(tool_name or ""):
            target_edges = [e for e in edges if e.get("target") == delegated_subagent]
            if target_edges:
                target_edge = target_edges[0]
                target_order = target_edge.get("order", 1)
                edge_id = target_edge.get("id", f"e_{delegated_subagent}")
                max_loops = target_edge.get("max_loops", 3)
                current_loops = state.get("edge_counts", {}).get(edge_id, 0)

                if current_loops >= max_loops:
                    msg = (
                        f"[HarnessForge Topology Guard] Max loop count ({max_loops}) exceeded "
                        f"for transition -> `{delegated_subagent}`."
                    )
                    state["violations_blocked"] = state.get("violations_blocked", 0) + 1
                    save_json(STATE_PATH, state)
                    emit_telemetry(
                        config,
                        {
                            "run_id": config.get("run_id", "preview-run"),
                            "timestamp": utc_now(),
                            "source": "hook",
                            "event_type": "TopologyViolation",
                            "agent_id": active_agent,
                            "tool_name": tool_name,
                            "tool_input": tool_input,
                            "status": "blocked",
                            "duration_ms": elapsed_ms,
                            "message": msg,
                        },
                    )
                    if is_antigravity:
                        print_hook_stdout(True, "PreToolUse", decision="deny", reason=msg)
                        return 0
                    sys.stderr.write(msg + "\\n")
                    return 2

                for prior in edges:
                    if prior.get("order", 1) < target_order and prior.get("required", True):
                        req_target = prior.get("target")
                        if req_target and req_target in subagents and req_target not in visited:
                            msg = (
                                f"[HarnessForge Topology Guard] Out-of-order subagent call blocked: "
                                f"Cannot invoke `{delegated_subagent}` (Step {target_order}) before required "
                                f"subagent `{req_target}` (Step {prior.get('order')}) has run."
                            )
                            state["violations_blocked"] = state.get("violations_blocked", 0) + 1
                            save_json(STATE_PATH, state)
                            emit_telemetry(
                                config,
                                {
                                    "run_id": config.get("run_id", "preview-run"),
                                    "timestamp": utc_now(),
                                    "source": "hook",
                                    "event_type": "TopologyViolation",
                                    "agent_id": active_agent,
                                    "tool_name": tool_name,
                                    "tool_input": tool_input,
                                    "status": "blocked",
                                    "duration_ms": elapsed_ms,
                                    "message": msg,
                                },
                            )
                            if is_antigravity:
                                print_hook_stdout(True, "PreToolUse", decision="deny", reason=msg)
                                return 0
                            sys.stderr.write(msg + "\\n")
                            return 2

                state.setdefault("edge_counts", {})[edge_id] = current_loops + 1

        state["active_agent"] = delegated_subagent
        if delegated_subagent not in state.get("visited_nodes", []):
            state.setdefault("visited_nodes", []).append(delegated_subagent)
        save_json(STATE_PATH, state)
        in_tok, out_tok, cost_usd = estimate_tool_tokens(tool_name, tool_input)
        emit_telemetry(
            config,
            {
                "run_id": config.get("run_id", "preview-run"),
                "timestamp": utc_now(),
                "source": "hook",
                "event_type": "SubagentStart",
                "agent_id": delegated_subagent,
                "tool_name": tool_name,
                "tool_input": tool_input,
                "status": "ok",
                "duration_ms": elapsed_ms,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cost_usd": cost_usd,
                "message": f"Handoff to subagent `{delegated_subagent}`",
            },
        )
        print_hook_stdout(is_antigravity, "PreToolUse", decision="allow")
        return 0

    # Check custom architecture hooks & permission boundaries on PreToolUse
    if hook_event == "PreToolUse" and enforce:
        agent_cfg = (
            config.get("orchestrator", {})
            if active_agent == "root_orchestrator"
            else subagents.get(active_agent, {})
        )
        if WRITE_TOOL_PATTERNS.match(tool_name) and not agent_cfg.get("allow_write", True):
            msg = (
                f"[HarnessForge Guardrail] Agent `{active_agent}` has `allow_write: false` "
                f"and cannot invoke `{tool_name}`. Delegate file modifications to an authorized coding subagent."
            )
            state["violations_blocked"] = state.get("violations_blocked", 0) + 1
            save_json(STATE_PATH, state)
            emit_telemetry(
                config,
                {
                    "run_id": config.get("run_id", "preview-run"),
                    "timestamp": utc_now(),
                    "source": "hook",
                    "event_type": "TopologyViolation",
                    "agent_id": active_agent,
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "status": "blocked",
                    "duration_ms": elapsed_ms,
                    "message": msg,
                },
            )
            if is_antigravity:
                print_hook_stdout(True, "PreToolUse", decision="deny", reason=msg)
                return 0
            sys.stderr.write(msg + "\\n")
            return 2

        if SHELL_TOOL_PATTERNS.match(tool_name):
            if not agent_cfg.get("allow_shell", True):
                msg = f"[HarnessForge Guardrail] Agent `{active_agent}` has `allow_shell: false`."
                state["violations_blocked"] = state.get("violations_blocked", 0) + 1
                save_json(STATE_PATH, state)
                emit_telemetry(
                    config,
                    {
                        "run_id": config.get("run_id", "preview-run"),
                        "timestamp": utc_now(),
                        "source": "hook",
                        "event_type": "TopologyViolation",
                        "agent_id": active_agent,
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "status": "blocked",
                        "duration_ms": elapsed_ms,
                        "message": msg,
                    },
                )
                if is_antigravity:
                    print_hook_stdout(True, "PreToolUse", decision="deny", reason=msg)
                    return 0
                sys.stderr.write(msg + "\\n")
                return 2

            cmd_str = str(tool_input.get("command") or tool_input.get("CommandLine") or "")
            for blocked_sub in agent_cfg.get("blocked_commands", []):
                if blocked_sub and blocked_sub in cmd_str:
                    msg = f"[HarnessForge Guardrail] Blocked dangerous command substring: `{blocked_sub}`"
                    if is_antigravity:
                        print_hook_stdout(True, "PreToolUse", decision="deny", reason=msg)
                        return 0
                    sys.stderr.write(msg + "\\n")
                    return 2

        for hook in config.get("hooks", []):
            if hook.get("event") == "PreToolUse" and hook.get("action") == "block":
                target_ag = hook.get("target_agent", "*")
                if target_ag in ("*", active_agent):
                    matcher = hook.get("matcher", ".*")
                    if re.search(matcher, tool_name, re.IGNORECASE):
                        if target_ag == active_agent and not agent_cfg.get("allow_write", True):
                            msg = f"[HarnessForge Hook `{hook.get('id')}`] {hook.get('message')}"
                            if is_antigravity:
                                print_hook_stdout(True, "PreToolUse", decision="deny", reason=msg)
                                return 0
                            sys.stderr.write(msg + "\\n")
                            return 2

    if hook_event == "SubagentStop":
        finished_agent = active_agent
        state["active_agent"] = "root_orchestrator"
        save_json(STATE_PATH, state)
        emit_telemetry(
            config,
            {
                "run_id": config.get("run_id", "preview-run"),
                "timestamp": utc_now(),
                "source": "hook",
                "event_type": "SubagentStop",
                "agent_id": finished_agent,
                "status": "ok",
                "duration_ms": elapsed_ms,
                "message": f"Subagent `{finished_agent}` returned control to `root_orchestrator`",
            },
        )
        return 0

    if hook_event == "Stop":
        visited = set(state.get("visited_nodes", []))
        last_input = str(stdin_data.get("lastUserInput") or "").lower()
        is_health_check_turn = (
            "verify-setup" in last_input
            or "verify setup" in last_input
            or "evaluate-project" in last_input
        )
        if enforce and not is_health_check_turn and not is_antigravity:
            for edge in config.get("edges", []):
                target = edge.get("target")
                if edge.get("required", True) and target in subagents and target not in visited:
                    if not state.get("stop_warned"):
                        state["stop_warned"] = True
                        save_json(STATE_PATH, state)
                        msg = (
                            f"[HarnessForge Topology Guard] Cannot complete task yet: required subagent "
                            f"`{target}` has not been invoked."
                        )
                        emit_telemetry(
                            config,
                            {
                                "run_id": config.get("run_id", "preview-run"),
                                "timestamp": utc_now(),
                                "source": "hook",
                                "event_type": "TopologyViolation",
                                "agent_id": "root_orchestrator",
                                "status": "blocked",
                                "duration_ms": elapsed_ms,
                                "message": msg,
                            },
                        )
                        sys.stderr.write(msg + "\\n")
                        return 2

        emit_telemetry(
            config,
            {
                "run_id": config.get("run_id", "preview-run"),
                "timestamp": utc_now(),
                "source": "hook",
                "event_type": "SessionStop",
                "agent_id": "root_orchestrator",
                "status": "ok",
                "duration_ms": elapsed_ms,
                "message": "Harness session completed",
            },
        )
        print_hook_stdout(is_antigravity, "Stop", decision="allow")
        return 0

    # Record standard PreToolUse / PostToolUse telemetry
    if hook_event in ("PreToolUse", "PostToolUse"):
        # When an invoke_subagent / Task / Agent call completes in PostToolUse, return active_agent to root_orchestrator
        if hook_event == "PostToolUse" and SUBAGENT_TOOL_PATTERNS.match(tool_name or ""):
            finished_agent = state.get("active_agent", "root_orchestrator")
            state["active_agent"] = "root_orchestrator"
            save_json(STATE_PATH, state)
            emit_telemetry(
                config,
                {
                    "run_id": config.get("run_id", "preview-run"),
                    "timestamp": utc_now(),
                    "source": "hook",
                    "event_type": "SubagentStop",
                    "agent_id": finished_agent,
                    "tool_name": tool_name,
                    "status": "ok",
                    "duration_ms": elapsed_ms,
                    "message": f"Subagent `{finished_agent}` completed delegation",
                },
            )
            print_hook_stdout(is_antigravity, "PostToolUse", decision="allow")
            return 0

        in_tok, out_tok, cost_usd = (0, 0, 0.0)
        if hook_event == "PreToolUse":
            state["tool_calls_count"] = state.get("tool_calls_count", 0) + 1
            save_json(STATE_PATH, state)
            in_tok, out_tok, cost_usd = estimate_tool_tokens(tool_name, tool_input)
        emit_telemetry(
            config,
            {
                "run_id": config.get("run_id", "preview-run"),
                "timestamp": utc_now(),
                "source": "hook",
                "event_type": hook_event,
                "agent_id": active_agent,
                "tool_name": tool_name or "tool",
                "tool_input": tool_input,
                "status": "ok",
                "duration_ms": elapsed_ms if hook_event == "PreToolUse" else 45.0,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cost_usd": cost_usd,
            },
        )
        print_hook_stdout(is_antigravity, hook_event, decision="allow")

    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

    return [
        CompiledFile(
            relative_path=".harness-eval/topology_config.json",
            content=json.dumps(topology_config, indent=2),
            description="Compiled topology state machine, permissions, and telemetry endpoint config",
        ),
        CompiledFile(
            relative_path=".harness-eval/state.json",
            content=json.dumps(initial_state, indent=2),
            description="Initial runtime state for tracking active node, visited subagents, and loop counters",
        ),
        CompiledFile(
            relative_path=".harness-eval/hook_runner.py",
            content=hook_runner_script,
            description="Dual-mode runtime topology guardrail and real-time telemetry hook emitter",
            executable=True,
        ),
    ]
