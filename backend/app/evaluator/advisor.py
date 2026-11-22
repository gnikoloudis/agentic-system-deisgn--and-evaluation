"""Layer 4: Full Evaluation Pipeline Orchestrator, Side-by-Side A/B Matrix, and AI Architecture Advisor."""

from __future__ import annotations

import copy
import difflib
from pathlib import Path
from typing import Any, Dict, List

from app.db.database import (
    get_run,
    list_telemetry_events,
    save_advisor_suggestion,
    update_run_status,
    utc_now_iso,
)
from app.db.storage import blueprint_to_yaml, get_blueprint, get_task
from app.evaluator.deterministic import run_deterministic_verifiers
from app.evaluator.judge import evaluate_with_judge
from app.evaluator.trajectory import analyze_trajectory_and_topology
from app.runner.sandbox import extract_sandbox_git_diff
from app.runner.transcript_parsers import ingest_local_telemetry_jsonl
from app.schemas.blueprint import (
    AgentArchitecture,
    AgentPermissions,
    HookSpec,
    NodePosition,
    SubagentSpec,
    TopologyEdge,
)
from app.schemas.evaluation import (
    ABComparisonResponse,
    AdvisorDiagnosisItem,
    AdvisorSuggestion,
    EvaluationReport,
    RunRecordSchema,
)


def evaluate_completed_run(run_id: str) -> EvaluationReport:
    """Execute all 4 evaluation layers on a run and persist the resulting EvaluationReport."""
    run = get_run(run_id)
    if not run:
        raise ValueError(f"Run '{run_id}' not found")

    bp_tuple = get_blueprint(run.architecture_id)
    if not bp_tuple:
        raise ValueError(f"Blueprint '{run.architecture_id}' not found")
    blueprint, _, _ = bp_tuple

    task_tuple = get_task(run.task_id)
    if not task_tuple:
        raise ValueError(f"Task '{run.task_id}' not found")
    task, _, _ = task_tuple

    sandbox_dir = Path(run.sandbox_path)
    git_diff, changed_files = extract_sandbox_git_diff(sandbox_dir)
    if not git_diff and run.git_diff:
        git_diff = run.git_diff
        changed_files = run.changed_files

    # Merge any locally written hook events from .harness-eval/telemetry.jsonl
    events = list_telemetry_events(run_id)
    local_extra = ingest_local_telemetry_jsonl(run_id, sandbox_dir, existing_count=len(events))
    events.extend(local_extra)

    # Layer 1: Deterministic Verifiers
    verifier_results, deterministic_score, all_required_passed = run_deterministic_verifiers(
        task.verifiers, sandbox_dir, git_diff
    )

    # Layer 2: Trajectory & Topology Metrics
    trajectory = analyze_trajectory_and_topology(blueprint, events)
    topology_pct = round(trajectory.topology_adherence_score * 100.0, 2)
    efficiency_pct = round(trajectory.efficiency_score * 100.0, 2)

    # Layer 3: LLM-as-a-Judge
    judge_eval = evaluate_with_judge(
        blueprint=blueprint,
        task=task,
        verifiers=verifier_results,
        deterministic_score=deterministic_score,
        trajectory=trajectory,
        git_diff=git_diff,
    )

    # Composite Score: 45% Deterministic + 20% Topology Adherence + 15% Efficiency + 20% Judge
    composite = round(
        (0.45 * deterministic_score)
        + (0.20 * topology_pct)
        + (0.15 * efficiency_pct)
        + (0.20 * judge_eval.overall_judge_score),
        2,
    )

    report = EvaluationReport(
        run_id=run_id,
        architecture_id=blueprint.metadata.id,
        architecture_name=blueprint.metadata.name,
        task_id=task.id,
        task_name=task.name,
        harness=run.harness,
        evaluated_at=utc_now_iso(),
        overall_composite_score=composite,
        deterministic_score=deterministic_score,
        topology_adherence_pct=topology_pct,
        efficiency_pct=efficiency_pct,
        judge_score=judge_eval.overall_judge_score,
        all_required_verifiers_passed=all_required_passed,
        verifier_results=verifier_results,
        trajectory=trajectory,
        judge=judge_eval,
        git_diff=git_diff,
        changed_files=changed_files,
    )

    update_run_status(
        run_id=run_id,
        status="completed",
        completed_at=run.completed_at or utc_now_iso(),
        git_diff=git_diff,
        changed_files=changed_files,
        evaluation=report,
    )
    return report


def compare_runs_ab(run_ids: List[str]) -> ABComparisonResponse:
    """Build a side-by-side A/B comparison matrix across multiple architectures or harnesses."""
    runs: List[RunRecordSchema] = []
    for rid in run_ids:
        r = get_run(rid)
        if r:
            if not r.evaluation:
                evaluate_completed_run(rid)
                r = get_run(rid)
            if r:
                runs.append(r)

    if not runs:
        return ABComparisonResponse(run_ids=run_ids, runs=[])

    # Determine winner by highest overall_composite_score, breaking ties by lower cost
    scored_runs = [r for r in runs if r.evaluation is not None]
    winner = None
    if scored_runs:
        winner = sorted(
            scored_runs,
            key=lambda x: (
                x.evaluation.overall_composite_score if x.evaluation else 0.0,
                -(x.evaluation.trajectory.total_cost_usd if x.evaluation else 999.0),
            ),
            reverse=True,
        )[0]

    matrix: Dict[str, Dict[str, Any]] = {}
    for r in runs:
        ev = r.evaluation
        matrix[r.id] = {
            "run_id": r.id,
            "architecture_id": r.architecture_id,
            "architecture_name": r.architecture_name,
            "harness": r.harness,
            "task_name": r.task_name,
            "overall_composite_score": ev.overall_composite_score if ev else 0.0,
            "deterministic_score": ev.deterministic_score if ev else 0.0,
            "topology_adherence_pct": ev.topology_adherence_pct if ev else 0.0,
            "efficiency_pct": ev.efficiency_pct if ev else 0.0,
            "judge_score": ev.judge_score if ev else 0.0,
            "total_tokens": ev.trajectory.total_tokens if ev else 0,
            "total_cost_usd": ev.trajectory.total_cost_usd if ev else 0.0,
            "total_duration_ms": ev.trajectory.total_duration_ms if ev else 0.0,
            "handoffs_count": ev.trajectory.handoffs_count if ev else 0,
            "subagents_count": len(ev.trajectory.per_node_breakdown) - 1 if ev else 0,
            "all_verifiers_passed": ev.all_required_verifiers_passed if ev else False,
        }

    takeaways: List[str] = []
    if winner and winner.evaluation:
        takeaways.append(
            f"Top Performer: `{winner.architecture_name}` on `{winner.harness}` with a composite score of "
            f"{winner.evaluation.overall_composite_score:.1f}/100 (${winner.evaluation.trajectory.total_cost_usd:.4f})."
        )
    if len(scored_runs) >= 2:
        cheapest = min(scored_runs, key=lambda r: r.evaluation.trajectory.total_cost_usd if r.evaluation else 999)
        fastest = min(scored_runs, key=lambda r: r.evaluation.trajectory.total_duration_ms if r.evaluation else 9e9)
        if cheapest.evaluation:
            takeaways.append(
                f"Most Cost-Efficient: `{cheapest.architecture_name}` ({cheapest.harness}) at "
                f"${cheapest.evaluation.trajectory.total_cost_usd:.4f} ({cheapest.evaluation.trajectory.total_tokens} tokens)."
            )
        if fastest.evaluation:
            takeaways.append(
                f"Lowest Latency: `{fastest.architecture_name}` ({fastest.harness}) completed in "
                f"{fastest.evaluation.trajectory.total_duration_ms:.0f} ms."
            )

    return ABComparisonResponse(
        run_ids=run_ids,
        runs=runs,
        winner_run_id=winner.id if winner else None,
        comparison_matrix=matrix,
        key_takeaways=takeaways,
    )


def _bump_minor_version(version_str: str) -> str:
    parts = version_str.split(".")
    if len(parts) == 3 and parts[1].isdigit():
        return f"{parts[0]}.{int(parts[1]) + 1}.0"
    return f"{version_str}-v2"


def generate_advisor_suggestion(run_id: str) -> AdvisorSuggestion:
    """Analyze a run's evaluation report and generate an actionable v2 AgentArchitecture blueprint + YAML diff."""
    run = get_run(run_id)
    if not run:
        raise ValueError(f"Run '{run_id}' not found")
    if not run.evaluation:
        evaluate_completed_run(run_id)
        run = get_run(run_id)
    assert run and run.evaluation

    bp_tuple = get_blueprint(run.architecture_id)
    if not bp_tuple:
        raise ValueError(f"Blueprint '{run.architecture_id}' not found")
    base_bp, base_yaml, _ = bp_tuple
    ev = run.evaluation

    proposed_bp: AgentArchitecture = copy.deepcopy(base_bp)
    new_version = _bump_minor_version(base_bp.metadata.version)
    proposed_bp.metadata.version = new_version

    diagnoses: List[AdvisorDiagnosisItem] = []
    changes_made: List[str] = []

    # Diagnosis 1: If architecture is a Solo Agent (no subagents), propose upgrading to a Generator-Verifier loop!
    if len(proposed_bp.subagents) == 0:
        diagnoses.append(
            AdvisorDiagnosisItem(
                severity="critical",
                target_component="topology / subagents",
                finding="Single-agent architecture has no independent Verifier critic; root agent edits and self-grades in the same context window.",
                recommendation="Add a dedicated `verifier` QA subagent and a Stop guardrail hook requiring `VERDICT: PASS` before task completion.",
            )
        )
        verifier_sa = SubagentSpec(
            id="verifier",
            name="Independent QA Verifier",
            role="Executes pytest and audits git diff for regressions before approving task completion",
            model="fast",
            system_prompt=(
                "You are the Independent QA Verifier. Run `pytest -v` and inspect `git diff`. "
                "Never modify files. Reply with `VERDICT: PASS` if all tests pass, or `VERDICT: FAIL` with defect details."
            ),
            tools=["read", "grep", "bash"],
            permissions=AgentPermissions(allow_shell=True, allow_write=False),
            max_turns=10,
        )
        proposed_bp.subagents.append(verifier_sa)
        proposed_bp.topology.pattern = "generator-verifier-loop"
        proposed_bp.topology.edges.append(
            TopologyEdge(
                id="e_auto_verify",
                source=proposed_bp.orchestrator.id,
                target="verifier",
                condition="After code edits are complete, before finishing task",
                order=len(proposed_bp.topology.edges) + 1,
                required=True,
                max_loops=2,
            )
        )
        proposed_bp.visual_layout.nodes["verifier"] = NodePosition(x=680, y=260)
        changes_made.append("Added `verifier` QA Critic subagent (`fast` model tier, read + pytest permissions)")
        changes_made.append("Added required topology edge `root_orchestrator -> verifier` (max_loops: 2)")

    # Diagnosis 2: Project-Specific Deliverable & Verifier Diagnostics
    if not ev.all_required_verifiers_passed:
        for vr in ev.verifier_results:
            if not vr.passed:
                diag_detail = (vr.output or "Check did not pass").strip().replace("\n", " | ")[:320]
                diagnoses.append(
                    AdvisorDiagnosisItem(
                        severity="critical",
                        target_component=f"verifier:{vr.check_id}",
                        finding=f"Project deliverable failed `{vr.name}`: {diag_detail}",
                        recommendation=(
                            "Update the responsible authoring subagent's system prompt with an explicit mandatory "
                            f"output template enforcing `{vr.name}` before returning control."
                        ),
                    )
                )
                # Inject specific improvements into user_story_author or workflow_architect if present
                for sa in proposed_bp.subagents:
                    if vr.type in ("user_story_invest_check", "markdown_sections_present") and (
                        "story" in sa.id or "coder" in sa.id or "consultant" in sa.id
                    ):
                        patch_note = (
                            f"\n\n[PROJECT IMPROVEMENT GATE — {vr.check_id}]: Ensure your deliverable strictly "
                            "includes Connextra ('As a... I want... So that...') user stories, Ron Jeffries' 3 Cs "
                            "(Card, Conversation for Dev, Confirmation with Given/When/Then BDD & TC-xxx IDs for QA), "
                            "Bill Wake's INVEST checklist, Definition of Ready, Definition of Done, and Traceability Matrix."
                        )
                        if vr.check_id not in sa.system_prompt:
                            sa.system_prompt = sa.system_prompt.rstrip() + patch_note
                            changes_made.append(
                                f"Strengthened subagent `{sa.id}` prompt to resolve `{vr.name}` failures in project"
                            )
                    elif vr.type == "mermaid_diagram_valid" and ("workflow" in sa.id or "architect" in sa.id):
                        patch_note = (
                            "\n\n[PROJECT IMPROVEMENT GATE — Mermaid Workflows]: Always include fenced ```mermaid "
                            "blocks for `flowchart TD`, `sequenceDiagram`, and `stateDiagram-v2` with valid `-->` and `->>` transitions."
                        )
                        if "PROJECT IMPROVEMENT GATE — Mermaid" not in sa.system_prompt:
                            sa.system_prompt = sa.system_prompt.rstrip() + patch_note
                            changes_made.append(
                                f"Strengthened subagent `{sa.id}` prompt to guarantee valid Mermaid workflow diagrams"
                            )

        proposed_bp.orchestrator.system_prompt = (
            proposed_bp.orchestrator.system_prompt.rstrip()
            + "\n\nCRITICAL VERIFICATION GATE: Before concluding, verify that all required project deliverables "
            "and test suites pass 100% of verification checks."
        )
        changes_made.append("Enhanced `root_orchestrator` system prompt with explicit `CRITICAL VERIFICATION GATE`")

    # Diagnosis 2.5: Detect skipped subagents in the project trajectory
    if ev.trajectory.expected_edges_traversed < ev.trajectory.expected_edges_total:
        visited_node_ids = {
            nb.node_id for nb in ev.trajectory.per_node_breakdown if nb.invocations > 0
        }
        skipped_subagents = [
            sa.id for sa in proposed_bp.subagents if sa.id not in visited_node_ids
        ]
        if skipped_subagents:
            diagnoses.append(
                AdvisorDiagnosisItem(
                    severity="warning",
                    target_component="topology.edges",
                    finding=(
                        f"During project execution, {len(skipped_subagents)} specialized subagent(s) were bypassed "
                        f"by the orchestrator: {', '.join(skipped_subagents)}."
                    ),
                    recommendation=(
                        "Switch `topology.enforcement_mode` to `dual` and add a `Stop` guardrail hook blocking completion "
                        f"until `{', '.join(skipped_subagents)}` have executed."
                    ),
                )
            )
            proposed_bp.topology.enforcement_mode = "dual"
            if not any(h.id == "require_all_subagents_before_stop" for h in proposed_bp.hooks):
                proposed_bp.hooks.append(
                    HookSpec(
                        id="require_all_subagents_before_stop",
                        event="Stop",
                        matcher=".*",
                        target_agent="root_orchestrator",
                        action="block",
                        message=f"Cannot finish session until all required subagents ({', '.join(skipped_subagents)}) have run.",
                    )
                )
            changes_made.append(
                f"Added `Stop` guardrail hook requiring bypassed subagent(s) ({', '.join(skipped_subagents)}) to execute"
            )

    # Diagnosis 3: Check token concentration or missing delegation guardrails
    if proposed_bp.subagents and proposed_bp.orchestrator.permissions.allow_write:
        diagnoses.append(
            AdvisorDiagnosisItem(
                severity="warning",
                target_component="root_orchestrator.permissions",
                finding="Root orchestrator has `allow_write: true` despite having specialized subagents, risking direct-edit bypass of subagent topology.",
                recommendation="Set `root_orchestrator.permissions.allow_write = false` and add a PreToolUse delegation guardrail hook.",
            )
        )
        proposed_bp.orchestrator.permissions.allow_write = False
        if not any(h.id == "enforce_subagent_delegation" for h in proposed_bp.hooks):
            proposed_bp.hooks.append(
                HookSpec(
                    id="enforce_subagent_delegation",
                    event="PreToolUse",
                    matcher="Write|Edit",
                    target_agent="root_orchestrator",
                    action="block",
                    message="Root orchestrator must delegate file modifications to specialized coding subagents.",
                )
            )
        changes_made.append("Restricted `root_orchestrator.permissions.allow_write` to `false` to enforce clean subagent delegation")

    # Diagnosis 4: Optimize token & cost efficiency on read-only planner/critic subagents
    for sa in proposed_bp.subagents:
        if not sa.permissions.allow_write and sa.max_turns > 10:
            diagnoses.append(
                AdvisorDiagnosisItem(
                    severity="optimization",
                    target_component=f"subagent:{sa.id}",
                    finding=f"Read-only subagent `{sa.id}` has a high turn budget (`max_turns: {sa.max_turns}`), which can inflate context window token usage during exploration.",
                    recommendation=f"Tighten `{sa.id}.max_turns` from {sa.max_turns} to 10 and require concise structured bullet output.",
                )
            )
            sa.max_turns = 10
            if "Keep your output under 250 words" not in sa.system_prompt:
                sa.system_prompt = sa.system_prompt.rstrip() + "\nKeep your output under 250 words with exact file and line references."
            changes_made.append(f"Tuned read-only subagent `{sa.id}` (`max_turns: 10` + concise output constraint)")

    if not changes_made:
        diagnoses.append(
            AdvisorDiagnosisItem(
                severity="optimization",
                target_component="orchestrator.budgets",
                finding="Architecture passed all checks with high topology adherence; minor context compaction tuning can further reduce latency.",
                recommendation="Tune context compaction threshold to 75% and enforce dual-mode topology guardrails.",
            )
        )
        proposed_bp.orchestrator.budgets.context_compaction_threshold_pct = 75
        proposed_bp.topology.enforcement_mode = "dual"
        changes_made.append("Tuned `context_compaction_threshold_pct` to 75% and enabled `dual` topology enforcement")

    proposed_yaml = blueprint_to_yaml(proposed_bp)
    diff_lines = list(
        difflib.unified_diff(
            base_yaml.splitlines(keepends=True),
            proposed_yaml.splitlines(keepends=True),
            fromfile=f"{base_bp.metadata.id} (v{base_bp.metadata.version})",
            tofile=f"{proposed_bp.metadata.id} (v{new_version})",
        )
    )
    unified_diff = "".join(diff_lines)

    suggestion = AdvisorSuggestion(
        run_id=run_id,
        architecture_id=base_bp.metadata.id,
        base_version=base_bp.metadata.version,
        proposed_version=new_version,
        generated_at=utc_now_iso(),
        provider_used="harnessforge-advisor-v1",
        summary=(
            f"Generated v{new_version} blueprint for `{base_bp.metadata.name}` with {len(changes_made)} "
            f"targeted architectural improvement(s) based on run `{run_id}` telemetry."
        ),
        diagnoses=diagnoses,
        changes_made=changes_made,
        proposed_blueprint=proposed_bp,
        unified_yaml_diff=unified_diff,
    )
    save_advisor_suggestion(suggestion)
    return suggestion
