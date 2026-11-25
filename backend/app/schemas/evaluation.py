"""Schemas for Execution Runs, Telemetry Traces, Multi-Layer Evaluations, A/B Comparisons, and AI Advisor."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from app.schemas.blueprint import AgentArchitecture, HarnessType


RunMode = Literal["headless", "interactive", "simulated_benchmark"]
RunStatus = Literal[
    "pending",
    "preparing_sandbox",
    "running",
    "waiting_for_user",
    "evaluating",
    "completed",
    "failed",
    "cancelled",
]


class TelemetryEvent(BaseModel):
    """A normalized lifecycle or tool telemetry event captured via hooks or native transcript."""

    id: Optional[int] = None
    run_id: str
    timestamp: str
    source: Literal["hook", "transcript", "runner"] = "hook"
    event_type: Literal[
        "SessionStart",
        "SubagentStart",
        "PreToolUse",
        "PostToolUse",
        "TopologyViolation",
        "SubagentStop",
        "SessionStop",
        "AssistantThinking",
        "AssistantMessage",
        "CommandOutput",
        "Error",
    ]
    agent_id: str = Field(default="root_orchestrator", description="Active node/agent in the architecture")
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None
    status: Literal["ok", "blocked", "error", "info"] = "ok"
    duration_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VerifierCheckResult(BaseModel):
    check_id: str
    name: str
    type: str
    passed: bool
    required: bool
    weight: float
    exit_code: Optional[int] = None
    output: str = ""
    duration_ms: float = 0.0


class NodeMetricsBreakdown(BaseModel):
    """Per-agent / per-node resource and performance breakdown."""

    node_id: str
    node_name: str
    node_role: str
    invocations: int = 0
    tool_calls: int = 0
    failed_tool_calls: int = 0
    blocked_tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    token_share_pct: float = 0.0
    time_share_pct: float = 0.0


class TrajectoryMetrics(BaseModel):
    """Layer 2: Architecture & Trajectory Efficiency Metrics."""

    total_duration_ms: float = 0.0
    total_turns: int = 0
    total_tool_calls: int = 0
    failed_tool_calls: int = 0
    tool_retry_rate_pct: float = 0.0
    redundant_reads_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    handoffs_count: int = 0
    expected_edges_total: int = 0
    expected_edges_traversed: int = 0
    unplanned_transitions: int = 0
    topology_violations_blocked: int = 0
    loop_iterations: int = 0
    topology_adherence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="1.0 = exact match with designed graph topology and required edges",
    )
    efficiency_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Composite score based on low tool retry/thrashing rate and budget adherence",
    )
    per_node_breakdown: List[NodeMetricsBreakdown] = Field(default_factory=list)
    traversed_edges: List[Dict[str, Any]] = Field(default_factory=list)
    bottleneck_warnings: List[str] = Field(default_factory=list)


class JudgeDimensionScore(BaseModel):
    dimension_id: str
    name: str
    score: float = Field(..., ge=1.0, le=5.0, description="Score from 1.0 to 5.0")
    weight: float = 1.0
    rationale: str


class JudgeEvaluation(BaseModel):
    """Layer 3: LLM-as-a-Judge & Human Evaluation."""

    provider_used: str = "harness_cli"
    model_used: str = "default"
    overall_judge_score: float = Field(default=0.0, ge=0.0, le=100.0)
    dimension_scores: List[JudgeDimensionScore] = Field(default_factory=list)
    executive_summary: str = ""
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    human_rating: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    human_notes: Optional[str] = None


class EvaluationReport(BaseModel):
    """Full 4-Layer Evaluation Report for a completed run."""

    run_id: str
    architecture_id: str
    architecture_name: str
    task_id: str
    task_name: str
    harness: HarnessType
    evaluated_at: str
    # Composite & Layer Scores (0 - 100)
    overall_composite_score: float = 0.0
    deterministic_score: float = 0.0
    topology_adherence_pct: float = 0.0
    efficiency_pct: float = 0.0
    judge_score: float = 0.0
    all_required_verifiers_passed: bool = False
    # Detailed layers
    verifier_results: List[VerifierCheckResult] = Field(default_factory=list)
    trajectory: TrajectoryMetrics = Field(default_factory=TrajectoryMetrics)
    judge: JudgeEvaluation = Field(default_factory=JudgeEvaluation)
    git_diff: str = ""
    changed_files: List[str] = Field(default_factory=list)


class AdvisorDiagnosisItem(BaseModel):
    severity: Literal["critical", "warning", "optimization"]
    target_component: str
    finding: str
    recommendation: str


class AdvisorSuggestion(BaseModel):
    """AI Architecture Advisor output proposing an actionable v2 architecture blueprint."""

    run_id: str
    architecture_id: str
    base_version: str
    proposed_version: str
    generated_at: str
    provider_used: str
    summary: str
    diagnoses: List[AdvisorDiagnosisItem] = Field(default_factory=list)
    changes_made: List[str] = Field(default_factory=list)
    proposed_blueprint: AgentArchitecture
    unified_yaml_diff: str


class RunRecordSchema(BaseModel):
    id: str
    architecture_id: str
    architecture_name: str
    architecture_version: str
    task_id: str
    task_name: str
    harness: HarnessType
    mode: RunMode
    status: RunStatus
    sandbox_path: str
    cli_command: str
    started_at: str
    completed_at: Optional[str] = None
    git_diff: str = ""
    changed_files: List[str] = Field(default_factory=list)
    evaluation: Optional[EvaluationReport] = None
    error_message: Optional[str] = None


class StartRunRequest(BaseModel):
    architecture_id: str
    task_id: str
    harness: HarnessType = "claude_code"
    mode: RunMode = "headless"
    custom_prompt_override: Optional[str] = None
    auto_evaluate: bool = True


class HumanGradeRequest(BaseModel):
    rating: float = Field(..., ge=1.0, le=5.0)
    notes: str = ""


class ABComparisonResponse(BaseModel):
    run_ids: List[str]
    runs: List[RunRecordSchema]
    winner_run_id: Optional[str] = None
    comparison_matrix: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    key_takeaways: List[str] = Field(default_factory=list)


class PreflightCheckItem(BaseModel):
    id: str
    name: str
    status: Literal["pass", "warn", "fail"]
    message: str
    detail: Optional[str] = None


class PreflightCheckRequest(BaseModel):
    architecture_id: str
    task_id: str
    harness: HarnessType = "claude_code"
    mode: RunMode = "simulated_benchmark"


class PreflightCheckResponse(BaseModel):
    ready: bool
    checks: List[PreflightCheckItem] = Field(default_factory=list)
    active_run_id: Optional[str] = None
    stale_run_count: int = 0


class ActiveRunStatusResponse(BaseModel):
    has_active_run: bool
    active_run: Optional[RunRecordSchema] = None


class ClearStaleRunsResponse(BaseModel):
    cleared_count: int
    cleared_run_ids: List[str] = Field(default_factory=list)
    removed_orphan_sandboxes: int = 0
