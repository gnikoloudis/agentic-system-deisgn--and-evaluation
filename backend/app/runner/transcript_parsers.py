"""Native Harness Transcript & Stream JSONL Parsers (Claude Code, Antigravity, OpenCode)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.schemas.blueprint import HarnessType
from app.schemas.evaluation import TelemetryEvent


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def estimate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    model: str = "default",
) -> float:
    """Estimate token cost in USD using model-specific pricing across Claude Code, Antigravity, and OpenCode."""
    m = (model or "").lower()
    if "-free" in m:
        in_rate, out_rate, cache_rate = 0.15 / 1_000_000, 0.60 / 1_000_000, 0.02 / 1_000_000
    elif "opus" in m or "neon-xhigh" in m or "neon-high" in m or "hydrogen-high" in m or "reasoning" in m:
        in_rate, out_rate, cache_rate = 15.0 / 1_000_000, 75.0 / 1_000_000, 1.50 / 1_000_000
    elif "haiku" in m or "flash" in m or "lightning" in m or "fast" in m or "argon-low" in m:
        in_rate, out_rate, cache_rate = 0.80 / 1_000_000, 4.0 / 1_000_000, 0.08 / 1_000_000
    elif "argon-high" in m or "sonnet-5-5-high" in m:
        in_rate, out_rate, cache_rate = 4.0 / 1_000_000, 18.0 / 1_000_000, 0.40 / 1_000_000
    elif "big-pickle" in m:
        in_rate, out_rate, cache_rate = 1.80 / 1_000_000, 7.50 / 1_000_000, 0.18 / 1_000_000
    else:
        # Sonnet / Argon Medium / default tier
        in_rate, out_rate, cache_rate = 3.0 / 1_000_000, 15.0 / 1_000_000, 0.30 / 1_000_000
    return round(input_tokens * in_rate + output_tokens * out_rate + cache_read_tokens * cache_rate, 6)


def parse_stream_json_line(
    run_id: str,
    harness: HarnessType,
    raw_line: str,
    active_agent: str = "root_orchestrator",
) -> Optional[TelemetryEvent]:
    """Parse a single JSONL line from Claude Code (`stream-json`), Antigravity (`transcript.jsonl`), or OpenCode (`--format json`)."""
    line = raw_line.strip()
    if not line or not line.startswith("{"):
        return None
    try:
        payload: Dict[str, Any] = json.loads(line)
    except Exception:
        return None

    timestamp = payload.get("created_at") or payload.get("timestamp") or _utc_now()

    # 1. Claude Code stream-json / session JSONL format
    if harness == "claude_code" or "message" in payload or payload.get("type") in ("assistant", "result", "user"):
        msg = payload.get("message", payload)
        usage = msg.get("usage") or payload.get("usage") or {}
        in_tok = int(usage.get("input_tokens", 0) or 0)
        out_tok = int(usage.get("output_tokens", 0) or 0)
        cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
        cache_write = int(usage.get("cache_creation_input_tokens", 0) or 0)
        model_name = msg.get("model") or payload.get("model") or "claude-sonnet-4"
        cost = float(payload.get("total_cost_usd") or estimate_cost_usd(in_tok, out_tok, cache_read, model_name))

        content_blocks = msg.get("content", [])
        if isinstance(content_blocks, list):
            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "thinking":
                    return TelemetryEvent(
                        run_id=run_id,
                        timestamp=timestamp,
                        source="transcript",
                        event_type="AssistantThinking",
                        agent_id=active_agent,
                        status="info",
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        cache_read_tokens=cache_read,
                        cache_write_tokens=cache_write,
                        cost_usd=cost,
                        message=str(block.get("thinking", ""))[:500],
                    )
                if btype == "tool_use":
                    return TelemetryEvent(
                        run_id=run_id,
                        timestamp=timestamp,
                        source="transcript",
                        event_type="PreToolUse",
                        agent_id=active_agent,
                        tool_name=block.get("name", "tool"),
                        tool_input=block.get("input") if isinstance(block.get("input"), dict) else {},
                        status="ok",
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        cache_read_tokens=cache_read,
                        cache_write_tokens=cache_write,
                        cost_usd=cost,
                    )
                if btype == "text":
                    return TelemetryEvent(
                        run_id=run_id,
                        timestamp=timestamp,
                        source="transcript",
                        event_type="AssistantMessage",
                        agent_id=active_agent,
                        status="ok",
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        cache_read_tokens=cache_read,
                        cache_write_tokens=cache_write,
                        cost_usd=cost,
                        message=str(block.get("text", ""))[:800],
                    )

    # 2. Antigravity stream-json (`event`: `step_update` | `result`) and transcript.jsonl (`step_index`, `type`)
    if payload.get("event") in ("step_update", "result", "init"):
        ev_kind = payload.get("event")
        if ev_kind == "init":
            return None
        body = payload.get(ev_kind) or {}
        if not isinstance(body, dict):
            return None
        usage = body.get("usage") or {}
        in_tok = int(usage.get("input_tokens", 0) or 0)
        out_tok = int(usage.get("output_tokens", 0) or 0) + int(usage.get("thinking_tokens", 0) or 0)
        cache_read = int(usage.get("cache_read_tokens", 0) or 0)
        dur_ms = round(float(body.get("duration_seconds", 0.0) or 0.0) * 1000.0, 2)
        cost = estimate_cost_usd(in_tok, out_tok, cache_read, "pro")

        if ev_kind == "step_update":
            step_type = body.get("step_type", "")
            step_index = body.get("step_index")
            if step_type in ("user_input", "system_message"):
                return None
            text_delta = body.get("text_delta") or body.get("response") or ""
            tool_name = body.get("tool_name") or body.get("tool")
            tool_input = body.get("tool_input") if isinstance(body.get("tool_input"), dict) else {}

            if tool_name:
                t_name_str = str(tool_name)
                # Check if this tool call is delegating to a subagent
                if t_name_str in ("invoke_subagent", "Task", "Agent", "subagent"):
                    sub_id = (
                        tool_input.get("TypeName")
                        or tool_input.get("subagent_type")
                        or tool_input.get("name")
                        or tool_input.get("Role")
                        or "subagent"
                    )
                    role_desc = tool_input.get("Role") or ""
                    prompt_preview = str(tool_input.get("Prompt") or "")[:180]
                    msg = f"Delegating to subagent `{sub_id}`"
                    if role_desc and role_desc != sub_id:
                        msg += f" ({role_desc})"
                    if prompt_preview:
                        msg += f": {prompt_preview}..."
                    return TelemetryEvent(
                        run_id=run_id,
                        timestamp=timestamp,
                        source="transcript",
                        event_type="SubagentStart",
                        agent_id=str(sub_id),
                        tool_name=t_name_str,
                        tool_input=tool_input,
                        status="ok",
                        duration_ms=dur_ms,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        cache_read_tokens=cache_read,
                        cost_usd=cost,
                        message=msg,
                        metadata={"step_index": step_index},
                    )

                # Standard tool call summary
                arg_summary = ""
                for k in ("Path", "path", "file_path", "CommandLine", "command", "query", "Pattern"):
                    if k in tool_input and tool_input[k]:
                        arg_summary = f" -> `{str(tool_input[k])[:140]}`"
                        break
                msg = str(text_delta)[:400] if text_delta else f"Executing tool `{t_name_str}`{arg_summary}"
                return TelemetryEvent(
                    run_id=run_id,
                    timestamp=timestamp,
                    source="transcript",
                    event_type="PreToolUse",
                    agent_id=active_agent,
                    tool_name=t_name_str,
                    tool_input=tool_input,
                    status="ok",
                    duration_ms=dur_ms,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    cache_read_tokens=cache_read,
                    cost_usd=cost,
                    message=msg,
                    metadata={"step_index": step_index},
                )

            # Only emit AssistantMessage when there is actual text content (suppress empty 'Step #N' headers)
            if text_delta:
                return TelemetryEvent(
                    run_id=run_id,
                    timestamp=timestamp,
                    source="transcript",
                    event_type="AssistantMessage",
                    agent_id=active_agent,
                    status="ok",
                    duration_ms=dur_ms,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    cache_read_tokens=cache_read,
                    cost_usd=cost,
                    message=str(text_delta),
                    metadata={"step_index": step_index, "is_delta": True},
                )
            return None
        elif ev_kind == "result":
            resp_text = str(body.get("response") or "").strip()
            return TelemetryEvent(
                run_id=run_id,
                timestamp=timestamp,
                source="transcript",
                event_type="AssistantMessage",
                agent_id=active_agent,
                status="ok" if body.get("status") == "SUCCESS" else "error",
                duration_ms=dur_ms,
                input_tokens=in_tok,
                output_tokens=out_tok,
                cache_read_tokens=cache_read,
                cost_usd=cost,
                message=f"[Session Result: {body.get('status')}] {resp_text[:1000]}",
                metadata={"step_index": "final_result"},
            )

    if "step_index" in payload or payload.get("type") == "PLANNER_RESPONSE":
        thinking = payload.get("thinking")
        tool_calls = payload.get("tool_calls") or []
        content = payload.get("content") or ""
        in_tok = int(payload.get("input_tokens", 450))
        out_tok = int(payload.get("output_tokens", max(80, len(str(content)) // 4)))
        cost = estimate_cost_usd(in_tok, out_tok, 0, "pro")

        if tool_calls and isinstance(tool_calls, list):
            first_tc = tool_calls[0] if isinstance(tool_calls[0], dict) else {}
            t_name = first_tc.get("name") or first_tc.get("tool_name") or "tool"
            t_args = first_tc.get("arguments") or first_tc.get("args") or {}
            return TelemetryEvent(
                run_id=run_id,
                timestamp=timestamp,
                source="transcript",
                event_type="PreToolUse",
                agent_id=active_agent,
                tool_name=t_name,
                tool_input=t_args if isinstance(t_args, dict) else {"raw": str(t_args)},
                status="ok",
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=cost,
                message=str(thinking or content)[:500] if (thinking or content) else None,
            )
        if thinking or content:
            return TelemetryEvent(
                run_id=run_id,
                timestamp=timestamp,
                source="transcript",
                event_type="AssistantMessage",
                agent_id=active_agent,
                status="ok",
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=cost,
                message=str(content or thinking)[:800],
            )

    # 3. OpenCode JSON event format
    if harness == "opencode" or "part" in payload or "tokens" in payload:
        tokens = payload.get("tokens") or {}
        in_tok = int(tokens.get("input", 0) or 0)
        out_tok = int(tokens.get("output", 0) or 0)
        cache_read = int(tokens.get("cache", {}).get("read", 0) if isinstance(tokens.get("cache"), dict) else 0)
        cost = float(payload.get("cost") or estimate_cost_usd(in_tok, out_tok, cache_read))
        event_text = payload.get("text") or payload.get("content") or ""
        if event_text or in_tok or out_tok:
            return TelemetryEvent(
                run_id=run_id,
                timestamp=timestamp,
                source="transcript",
                event_type="AssistantMessage",
                agent_id=active_agent,
                status="ok",
                input_tokens=in_tok,
                output_tokens=out_tok,
                cache_read_tokens=cache_read,
                cost_usd=cost,
                message=str(event_text)[:800],
            )

    return None


def ingest_local_telemetry_jsonl(run_id: str, sandbox_dir: Path, existing_count: int = 0) -> List[TelemetryEvent]:
    """Ingest any events logged locally to .harness-eval/telemetry.jsonl that weren't received via HTTP."""
    jsonl_path = sandbox_dir / ".harness-eval" / "telemetry.jsonl"
    if not jsonl_path.exists():
        alt_path = sandbox_dir / ".agents" / ".harness-eval" / "telemetry.jsonl"
        if alt_path.exists():
            jsonl_path = alt_path
        else:
            return []
    lines = jsonl_path.read_text(encoding="utf-8", errors="replace").splitlines()
    events: List[TelemetryEvent] = []
    for line in lines[existing_count:]:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            data["run_id"] = run_id
            events.append(TelemetryEvent.model_validate(data))
        except Exception:
            continue
    return events
