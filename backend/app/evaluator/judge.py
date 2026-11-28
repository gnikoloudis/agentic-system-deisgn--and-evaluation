"""Layer 3: Dual-Provider LLM-as-a-Judge (Harness CLI or Direct API Key + Deterministic Analytic Fallback)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import List, Optional, Tuple

import httpx

from app.config import settings
from app.schemas.blueprint import AgentArchitecture
from app.schemas.evaluation import (
    JudgeDimensionScore,
    JudgeEvaluation,
    TrajectoryMetrics,
    VerifierCheckResult,
)
from app.schemas.task import TaskSpec


def _build_judge_prompt(
    blueprint: AgentArchitecture,
    task: TaskSpec,
    verifiers: List[VerifierCheckResult],
    trajectory: TrajectoryMetrics,
    git_diff: str,
) -> str:
    verifier_summary = "\n".join(
        f"- {v.name} ({v.type}): {'PASSED' if v.passed else 'FAILED'} — {v.output[:200]}"
        for v in verifiers
    )
    rubric_json = json.dumps([r.model_dump() for r in task.rubric], indent=2)
    return (
        "You are an expert Agentic Architecture Judge evaluating a coding harness execution.\n\n"
        f"## Architecture: {blueprint.metadata.name} ({blueprint.metadata.id})\n"
        f"Topology Pattern: {blueprint.topology.pattern} ({len(blueprint.subagents)} subagents)\n\n"
        f"## Task: {task.name}\n{task.prompt}\n\n"
        f"## Deterministic Verifier Results:\n{verifier_summary}\n\n"
        f"## Trajectory Metrics:\n"
        f"- Topology Adherence: {trajectory.topology_adherence_score * 100:.1f}%\n"
        f"- Total Tokens: {trajectory.total_tokens} (${trajectory.total_cost_usd:.4f})\n"
        f"- Handoffs: {trajectory.handoffs_count}, Failed Tools: {trajectory.failed_tool_calls}\n\n"
        f"## Git Diff:\n```diff\n{git_diff[:3000]}\n```\n\n"
        f"## Rubric Dimensions:\n{rubric_json}\n\n"
        "Respond ONLY with valid JSON matching keys: "
        "`dimension_scores` (list of {dimension_id, name, score (1.0-5.0), weight, rationale}), "
        "`executive_summary`, `strengths` (list of strings), `weaknesses` (list of strings)."
    )


def _try_invoke_llm_json(prompt: str) -> Optional[Tuple[dict, str, str]]:
    """Attempt to invoke either installed Harness CLI or Direct LLM API if configured."""
    cfg = settings.judge

    # 1. Try installed Harness CLI if mode == 'harness_cli'
    if cfg.mode == "harness_cli":
        binary_map = {
            "claude_code": settings.claude_binary,
            "opencode": settings.opencode_binary,
            "antigravity": settings.antigravity_binary,
        }
        bin_name = binary_map.get(cfg.harness_cli, "claude")
        resolved = shutil.which(bin_name)
        if resolved:
            try:
                if cfg.harness_cli == "claude_code":
                    cmd = [resolved, "-p", prompt, "--output-format", "text"]
                elif cfg.harness_cli == "opencode":
                    cmd = [resolved, "run", prompt]
                else:
                    cmd = [resolved, "-p", prompt, "--output-format", "text"]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45, encoding="utf-8")
                if proc.returncode == 0 and "{" in proc.stdout:
                    raw = proc.stdout
                    start, end = raw.find("{"), raw.rfind("}")
                    if start != -1 and end != -1:
                        return json.loads(raw[start : end + 1]), f"harness_cli:{cfg.harness_cli}", cfg.model
            except Exception:
                pass

    # 2. Try Direct API Key if mode == 'api_key' or API key is present
    api_key = cfg.api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if cfg.mode == "api_key" and api_key:
        try:
            if cfg.api_provider == "anthropic":
                resp = httpx.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": cfg.model,
                        "max_tokens": 1024,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    timeout=30.0,
                )
                if resp.status_code == 200:
                    text = resp.json()["content"][0]["text"]
                    s, e = text.find("{"), text.rfind("}")
                    if s != -1 and e != -1:
                        return json.loads(text[s : e + 1]), "api_key:anthropic", cfg.model
            else:
                base = (cfg.base_url or "https://api.openai.com/v1").rstrip("/")
                resp = httpx.post(
                    f"{base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": cfg.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                    },
                    timeout=30.0,
                )
                if resp.status_code == 200:
                    text = resp.json()["choices"][0]["message"]["content"]
                    return json.loads(text), f"api_key:{cfg.api_provider}", cfg.model
        except Exception:
            pass

    return None


def evaluate_with_judge(
    blueprint: AgentArchitecture,
    task: TaskSpec,
    verifiers: List[VerifierCheckResult],
    deterministic_score: float,
    trajectory: TrajectoryMetrics,
    git_diff: str,
) -> JudgeEvaluation:
    """Run LLM-as-a-Judge (via Harness CLI or API Key, with high-precision Analytic Rubric Judge fallback)."""
    prompt = _build_judge_prompt(blueprint, task, verifiers, trajectory, git_diff)
    llm_res = _try_invoke_llm_json(prompt)

    if llm_res:
        payload, provider_used, model_used = llm_res
        dim_scores: List[JudgeDimensionScore] = []
        for item in payload.get("dimension_scores", []):
            dim_scores.append(
                JudgeDimensionScore(
                    dimension_id=str(item.get("dimension_id", "dim")),
                    name=str(item.get("name", "Dimension")),
                    score=max(1.0, min(5.0, float(item.get("score", 4.0)))),
                    weight=float(item.get("weight", 1.0)),
                    rationale=str(item.get("rationale", "")),
                )
            )
        if dim_scores:
            total_w = sum(d.weight for d in dim_scores) or 1.0
            weighted_avg_1_5 = sum(d.score * d.weight for d in dim_scores) / total_w
            overall_pct = max(0.0, min(100.0, round(((weighted_avg_1_5 - 1.0) / 4.0) * 100.0, 2)))
            return JudgeEvaluation(
                provider_used=provider_used,
                model_used=model_used,
                overall_judge_score=overall_pct,
                dimension_scores=dim_scores,
                executive_summary=str(payload.get("executive_summary", "")),
                strengths=[str(x) for x in payload.get("strengths", [])],
                weaknesses=[str(x) for x in payload.get("weaknesses", [])],
            )

    # Analytic Rubric Judge (deterministic, zero-latency fallback when offline or no external CLI/key)
    all_passed = all(v.passed for v in verifiers) if verifiers else True
    has_subagents = len(blueprint.subagents) > 0
    has_verifier_node = any("verif" in sa.id.lower() or "test" in sa.id.lower() for sa in blueprint.subagents)

    correctness_score = round(1.0 + 4.0 * (deterministic_score / 100.0), 2)
    diff_lines = len([ln for ln in git_diff.splitlines() if ln.startswith("+") or ln.startswith("-")])
    clean_diff_factor = 1.0 if 2 <= diff_lines <= 80 else (0.75 if diff_lines > 80 else 0.4)
    quality_score = round(max(1.0, min(5.0, 2.0 + 2.2 * (deterministic_score / 100.0) + 0.8 * clean_diff_factor)), 2)

    orch_base = 1.5 + (2.5 * trajectory.topology_adherence_score)
    if has_subagents and has_verifier_node:
        orch_base += 0.8
    elif not has_subagents:
        orch_base -= 0.4  # Solo agent lacks specialized role separation & independent critic
    orch_score = round(max(1.0, min(5.0, orch_base)), 2)

    score_by_id = {
        "correctness": (
            correctness_score,
            f"Deterministic test/verifier pass rate was {deterministic_score:.1f}% ({'all required checks passed' if all_passed else 'some required checks failed'}).",
        ),
        "code_quality": (
            quality_score,
            f"Git diff modified {diff_lines} lines with tool efficiency score {trajectory.efficiency_score * 100:.1f}%.",
        ),
        "orchestration_fidelity": (
            orch_score,
            (
                f"Topology `{blueprint.topology.pattern}` executed {trajectory.handoffs_count} subagent handoff(s) "
                f"with {trajectory.topology_adherence_score * 100:.1f}% graph adherence."
            ),
        ),
    }

    dim_scores = []
    for rub in task.rubric:
        sc, rat = score_by_id.get(
            rub.id,
            (
                round((correctness_score + orch_score) / 2.0, 2),
                f"Evaluated {rub.name} against task outcomes and trace topology.",
            ),
        )
        dim_scores.append(
            JudgeDimensionScore(
                dimension_id=rub.id,
                name=rub.name,
                score=sc,
                weight=rub.weight,
                rationale=rat,
            )
        )

    total_w = sum(d.weight for d in dim_scores) or 1.0
    weighted_avg_1_5 = sum(d.score * d.weight for d in dim_scores) / total_w
    overall_pct = max(0.0, min(100.0, round(((weighted_avg_1_5 - 1.0) / 4.0) * 100.0, 2)))

    strengths: List[str] = []
    weaknesses: List[str] = []
    if all_passed:
        strengths.append("Passed 100% of deterministic test and git diff verifiers.")
    else:
        weaknesses.append("One or more deterministic verifiers failed.")
    if has_subagents and trajectory.topology_adherence_score >= 0.9:
        strengths.append(
            f"Strong multi-agent role separation across {len(blueprint.subagents)} subagents with clean handoffs."
        )
    if not has_subagents:
        weaknesses.append(
            "Single-agent architecture lacks an independent QA/Verifier subagent to catch regressions before completion."
        )
    if trajectory.topology_violations_blocked > 0:
        weaknesses.append(
            f"Triggered {trajectory.topology_violations_blocked} runtime hook guardrail block(s)."
        )

    return JudgeEvaluation(
        provider_used="analytic_rubric_engine",
        model_used="harnessforge-rubric-v1",
        overall_judge_score=overall_pct,
        dimension_scores=dim_scores,
        executive_summary=(
            f"Architecture `{blueprint.metadata.name}` achieved a {overall_pct:.1f}/100 Judge score "
            f"({deterministic_score:.1f}% deterministic checks, {trajectory.topology_adherence_score * 100:.1f}% topology adherence, "
            f"${trajectory.total_cost_usd:.4f} total cost across {trajectory.total_tokens} tokens)."
        ),
        strengths=strengths or ["Completed execution within budget constraints."],
        weaknesses=weaknesses or ["No major architectural defects observed in this run."],
    )
