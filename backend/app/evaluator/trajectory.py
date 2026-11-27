"""Layer 2: Trajectory, Per-Node Resource Breakdown, and Topology Adherence Analyzer."""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from app.schemas.blueprint import AgentArchitecture
from app.schemas.evaluation import NodeMetricsBreakdown, TelemetryEvent, TrajectoryMetrics


def analyze_trajectory_and_topology(
    blueprint: AgentArchitecture,
    events: List[TelemetryEvent],
) -> TrajectoryMetrics:
    """Compute per-node token/cost/time breakdowns, topology adherence score, and bottleneck diagnostics."""
    nodes_meta: Dict[str, Tuple[str, str]] = {
        blueprint.orchestrator.id: (blueprint.orchestrator.name, blueprint.orchestrator.role),
    }
    for sa in blueprint.subagents:
        nodes_meta[sa.id] = (sa.name, sa.role)

    node_stats: Dict[str, NodeMetricsBreakdown] = {
        node_id: NodeMetricsBreakdown(
            node_id=node_id,
            node_name=name,
            node_role=role,
            invocations=1 if node_id == blueprint.orchestrator.id else 0,
        )
        for node_id, (name, role) in nodes_meta.items()
    }

    total_duration_ms = 0.0
    total_turns = 0
    total_tool_calls = 0
    failed_tool_calls = 0
    topology_violations_blocked = 0
    handoffs_count = 0
    seen_read_paths: Set[str] = set()
    redundant_reads_count = 0

    visited_subagents: List[str] = []
    traversed_edges: List[Dict[str, object]] = []
    previous_agent = blueprint.orchestrator.id

    from datetime import datetime
    prev_event_dt = None

    for ev in events:
        ag_id = ev.agent_id or blueprint.orchestrator.id
        if ag_id not in node_stats:
            node_stats[ag_id] = NodeMetricsBreakdown(
                node_id=ag_id,
                node_name=ag_id,
                node_role="Dynamic Agent Node",
            )
        nb = node_stats[ag_id]

        # Backfill duration_ms from consecutive event timestamps if hook logged 0.0
        ev_dur = ev.duration_ms
        try:
            curr_dt = datetime.fromisoformat(ev.timestamp.replace("Z", "+00:00"))
            if ev_dur <= 0.0 and prev_event_dt is not None:
                ev_dur = round(max(85.0, min(25000.0, (curr_dt - prev_event_dt).total_seconds() * 1000.0)), 2)
            prev_event_dt = curr_dt
        except Exception:
            if ev_dur <= 0.0:
                ev_dur = 180.0

        # Backfill token estimates for legacy hook events that recorded 0 tokens
        in_t = ev.input_tokens
        out_t = ev.output_tokens
        cost_u = ev.cost_usd
        if ev.event_type in ("PreToolUse", "SubagentStart") and in_t == 0 and out_t == 0:
            from app.runner.transcript_parsers import estimate_cost_usd

            in_t = 480 if ev.event_type == "SubagentStart" else 340
            out_t = 320 if ev.event_type == "SubagentStart" else 160
            cost_u = estimate_cost_usd(in_t, out_t)

        nb.duration_ms += ev_dur
        nb.input_tokens += in_t
        nb.output_tokens += out_t
        nb.cache_read_tokens += ev.cache_read_tokens
        nb.total_tokens += in_t + out_t + ev.cache_read_tokens
        nb.cost_usd = round(nb.cost_usd + cost_u, 6)
        total_duration_ms += ev_dur

        if ev.event_type == "SubagentStart":
            nb.invocations += 1
            handoffs_count += 1
            visited_subagents.append(ag_id)
            traversed_edges.append(
                {
                    "source": previous_agent,
                    "target": ag_id,
                    "timestamp": ev.timestamp,
                    "message": ev.message or "",
                }
            )
            previous_agent = ag_id
        elif ev.event_type == "SubagentStop":
            previous_agent = blueprint.orchestrator.id
        elif ev.event_type in ("PreToolUse", "PostToolUse"):
            if ev.event_type == "PreToolUse":
                nb.tool_calls += 1
                total_tool_calls += 1
                total_turns += 1
                if (ev.tool_name or "").lower() in ("read", "read_file") and ev.tool_input:
                    p = str(ev.tool_input.get("path") or ev.tool_input.get("workspace") or "")
                    if p:
                        key = f"{ag_id}:{p}"
                        if key in seen_read_paths:
                            redundant_reads_count += 1
                        seen_read_paths.add(key)
            if ev.status == "error":
                nb.failed_tool_calls += 1
                failed_tool_calls += 1
        elif ev.event_type == "TopologyViolation" or ev.status == "blocked":
            nb.blocked_tool_calls += 1
            topology_violations_blocked += 1
        elif ev.event_type in ("AssistantThinking", "AssistantMessage"):
            total_turns += 1

    total_in = sum(n.input_tokens for n in node_stats.values())
    total_out = sum(n.output_tokens for n in node_stats.values())
    total_cache = sum(n.cache_read_tokens for n in node_stats.values())
    total_tok = total_in + total_out + total_cache
    total_cost = round(sum(n.cost_usd for n in node_stats.values()), 6)

    for nb in node_stats.values():
        nb.duration_ms = round(nb.duration_ms, 2)
        nb.token_share_pct = round((nb.total_tokens / total_tok) * 100.0, 1) if total_tok > 0 else 0.0
        nb.time_share_pct = round((nb.duration_ms / total_duration_ms) * 100.0, 1) if total_duration_ms > 0 else 0.0

    # Evaluate Topology Adherence against strictly Agent-to-Agent workflow handoff edges
    subagent_ids = {sa.id for sa in blueprint.subagents}
    workflow_edges = blueprint.workflow_handoff_edges()
    required_subagent_edges = [
        e for e in workflow_edges if e.required and e.target in subagent_ids
    ]
    expected_edges_total = len(required_subagent_edges)
    visited_set = set(visited_subagents)
    expected_edges_traversed = sum(1 for e in required_subagent_edges if e.target in visited_set)
    skipped_required = max(0, expected_edges_total - expected_edges_traversed)

    defined_targets = {e.target for e in workflow_edges}
    unplanned_transitions = sum(1 for sa_id in visited_subagents if defined_targets and sa_id not in defined_targets)
    loop_iterations = max(0, len(visited_subagents) - len(visited_set))

    denominator = max(1, handoffs_count + expected_edges_total + topology_violations_blocked)
    penalties = unplanned_transitions + topology_violations_blocked + skipped_required
    topology_adherence_score = round(max(0.0, min(1.0, 1.0 - (penalties / denominator))), 3)

    tool_retry_rate_pct = round((failed_tool_calls / total_tool_calls) * 100.0, 1) if total_tool_calls > 0 else 0.0
    budget_turn_ratio = total_turns / max(1, blueprint.orchestrator.budgets.max_turns)
    efficiency_penalty = (
        (failed_tool_calls * 0.08)
        + (redundant_reads_count * 0.04)
        + (max(0.0, budget_turn_ratio - 1.0) * 0.3)
    )
    efficiency_score = round(max(0.1, min(1.0, 1.0 - efficiency_penalty)), 3)

    # Generate diagnostic bottleneck warnings
    bottleneck_warnings: List[str] = []
    if not blueprint.subagents:
        bottleneck_warnings.append(
            "Single-agent topology (`solo`): Root orchestrator performed planning, editing, and verification in one shared context window without an independent Verifier subagent."
        )
    if skipped_required > 0:
        missing = [e.target for e in required_subagent_edges if e.target not in visited_set]
        bottleneck_warnings.append(
            f"Required subagent(s) skipped during run: {', '.join(missing)}."
        )
    if topology_violations_blocked > 0:
        bottleneck_warnings.append(
            f"Runtime hook guardrail blocked {topology_violations_blocked} out-of-policy tool/handoff attempt(s)."
        )
    if failed_tool_calls > 0:
        bottleneck_warnings.append(
            f"Observed {failed_tool_calls} failed tool execution(s) ({tool_retry_rate_pct}% failure rate)."
        )
    for nb in node_stats.values():
        if nb.token_share_pct > 70.0 and len(node_stats) > 1:
            bottleneck_warnings.append(
                f"Context concentration bottleneck: `{nb.node_id}` consumed {nb.token_share_pct}% of all session tokens."
            )

    return TrajectoryMetrics(
        total_duration_ms=round(total_duration_ms, 2),
        total_turns=total_turns,
        total_tool_calls=total_tool_calls,
        failed_tool_calls=failed_tool_calls,
        tool_retry_rate_pct=tool_retry_rate_pct,
        redundant_reads_count=redundant_reads_count,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        total_cache_read_tokens=total_cache,
        total_tokens=total_tok,
        total_cost_usd=total_cost,
        handoffs_count=handoffs_count,
        expected_edges_total=expected_edges_total,
        expected_edges_traversed=expected_edges_traversed,
        unplanned_transitions=unplanned_transitions,
        topology_violations_blocked=topology_violations_blocked,
        loop_iterations=loop_iterations,
        topology_adherence_score=topology_adherence_score,
        efficiency_score=efficiency_score,
        per_node_breakdown=list(node_stats.values()),
        traversed_edges=traversed_edges,
        bottleneck_warnings=bottleneck_warnings,
    )
