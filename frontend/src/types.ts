export type HarnessType = "claude_code" | "antigravity" | "opencode";
export type RunMode = "headless" | "interactive" | "simulated_benchmark";

export interface AgentPermissions {
  allow_shell: boolean;
  allow_write: boolean;
  allow_network: boolean;
  allowed_commands: string[];
  blocked_commands: string[];
}

export interface ExecutionBudgets {
  max_turns: number;
  max_cost_usd: number;
  timeout_seconds: number;
  context_compaction_threshold_pct: number;
}

export interface OrchestratorSpec {
  id: string;
  name: string;
  role: string;
  model: string;
  harness_models?: Record<string, string>;
  system_prompt: string;
  tools: string[];
  permissions: AgentPermissions;
  budgets: ExecutionBudgets;
}

export interface SubagentSpec {
  id: string;
  name: string;
  role: string;
  model: string;
  harness_models?: Record<string, string>;
  system_prompt: string;
  tools: string[];
  permissions: AgentPermissions;
  max_turns: number;
}

export interface EnterpriseProviderConfig {
  id: string;
  name: string;
  protocol: "openai_compatible";
  base_url: string;
  api_key_env: string;
  headers?: Record<string, string>;
  models: Array<{ id: string; name: string; tier?: string }>;
  enabled?: boolean;
}

export interface HarnessModelsConfig {
  tier_map: Record<HarnessType, Record<string, string>>;
  native_models: Record<HarnessType, Array<{ id: string; label: string; tier: string }>>;
  custom_providers?: EnterpriseProviderConfig[];
  best_practices: Record<string, string>;
}

export interface SkillSpec {
  id: string;
  name: string;
  description: string;
  instructions: string;
  source_dir?: string | null;
  trigger_command?: string | null;
}

export interface HookSpec {
  id: string;
  event: "PreToolUse" | "PostToolUse" | "SubagentStop" | "Stop" | "UserPromptSubmit";
  matcher: string;
  target_agent: string;
  action: "allow" | "block" | "run_command" | "warn";
  command?: string | null;
  message: string;
}

export interface MCPServerSpec {
  id: string;
  transport: "stdio" | "sse" | "http";
  command?: string | null;
  args: string[];
  url?: string | null;
  env: Record<string, string>;
}

export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
  condition: string;
  order: number;
  required: boolean;
  max_loops: number;
}

export interface TopologySpec {
  pattern:
    | "solo"
    | "sequential-pipeline"
    | "generator-verifier-loop"
    | "parallel-swarm"
    | "router-dispatcher"
    | "hierarchical-custom";
  enforcement_mode: "prompt" | "hook" | "dual";
  entry_node: string;
  edges: TopologyEdge[];
}

export interface AgentArchitecture {
  api_version: string;
  kind: "AgentArchitecture";
  metadata: {
    id: string;
    name: string;
    version: string;
    description: string;
    tags: string[];
    author: string;
  };
  orchestrator: OrchestratorSpec;
  subagents: SubagentSpec[];
  skills: SkillSpec[];
  hooks: HookSpec[];
  mcp_servers: MCPServerSpec[];
  topology: TopologySpec;
  visual_layout: {
    nodes: Record<string, { x: number; y: number }>;
  };
}

export interface CompiledFile {
  relative_path: string;
  content: string;
  description: string;
  executable: boolean;
}

export interface CompilationResult {
  architecture_id: string;
  architecture_version: string;
  harness: HarnessType;
  files: CompiledFile[];
  cli_preview_command: string;
  interactive_launch_command: string;
  notes: string[];
}

export interface VerificationCheck {
  id: string;
  name: string;
  type: string;
  command?: string | null;
  target_path?: string | null;
  pattern?: string | null;
  max_lines?: number | null;
  weight: number;
  required: boolean;
  timeout_seconds: number;
}

export interface TaskSpec {
  id: string;
  name: string;
  category: string;
  difficulty: "easy" | "medium" | "hard";
  description: string;
  prompt: string;
  workspace_source: string;
  expected_subagents: string[];
  verifiers: VerificationCheck[];
  tags: string[];
}

export interface TelemetryEvent {
  id?: number;
  run_id: string;
  timestamp: string;
  source: "hook" | "transcript" | "runner";
  event_type:
    | "SessionStart"
    | "SubagentStart"
    | "PreToolUse"
    | "PostToolUse"
    | "TopologyViolation"
    | "SubagentStop"
    | "SessionStop"
    | "AssistantThinking"
    | "AssistantMessage"
    | "CommandOutput"
    | "Error";
  agent_id: string;
  tool_name?: string | null;
  tool_input?: Record<string, unknown> | null;
  tool_output?: string | null;
  status: "ok" | "blocked" | "error" | "info";
  duration_ms: number;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cost_usd: number;
  message?: string | null;
}

export interface VerifierCheckResult {
  check_id: string;
  name: string;
  type: string;
  passed: boolean;
  required: boolean;
  weight: number;
  exit_code?: number | null;
  output: string;
  duration_ms: number;
}

export interface NodeMetricsBreakdown {
  node_id: string;
  node_name: string;
  node_role: string;
  invocations: number;
  tool_calls: number;
  failed_tool_calls: number;
  blocked_tool_calls: number;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  total_tokens: number;
  cost_usd: number;
  duration_ms: number;
  token_share_pct: number;
  time_share_pct: number;
}

export interface TrajectoryMetrics {
  total_duration_ms: number;
  total_turns: number;
  total_tool_calls: number;
  failed_tool_calls: number;
  tool_retry_rate_pct: number;
  redundant_reads_count: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cache_read_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  handoffs_count: number;
  expected_edges_total: number;
  expected_edges_traversed: number;
  unplanned_transitions: number;
  topology_violations_blocked: number;
  loop_iterations: number;
  topology_adherence_score: number;
  efficiency_score: number;
  per_node_breakdown: NodeMetricsBreakdown[];
  traversed_edges: Array<{ source: string; target: string; timestamp: string; message: string }>;
  bottleneck_warnings: string[];
}

export interface JudgeDimensionScore {
  dimension_id: string;
  name: string;
  score: number;
  weight: number;
  rationale: string;
}

export interface JudgeEvaluation {
  provider_used: string;
  model_used: string;
  overall_judge_score: number;
  dimension_scores: JudgeDimensionScore[];
  executive_summary: string;
  strengths: string[];
  weaknesses: string[];
  human_rating?: number | null;
  human_notes?: string | null;
}

export interface EvaluationReport {
  run_id: string;
  architecture_id: string;
  architecture_name: string;
  task_id: string;
  task_name: string;
  harness: HarnessType;
  evaluated_at: string;
  overall_composite_score: number;
  deterministic_score: number;
  topology_adherence_pct: number;
  efficiency_pct: number;
  judge_score: number;
  all_required_verifiers_passed: boolean;
  verifier_results: VerifierCheckResult[];
  trajectory: TrajectoryMetrics;
  judge: JudgeEvaluation;
  git_diff: string;
  changed_files: string[];
}

export interface RunRecord {
  id: string;
  architecture_id: string;
  architecture_name: string;
  architecture_version: string;
  task_id: string;
  task_name: string;
  harness: HarnessType;
  mode: RunMode;
  status: string;
  sandbox_path: string;
  cli_command: string;
  started_at: string;
  completed_at?: string | null;
  git_diff: string;
  changed_files: string[];
  evaluation?: EvaluationReport | null;
  error_message?: string | null;
}

export interface AdvisorSuggestion {
  run_id: string;
  architecture_id: string;
  base_version: string;
  proposed_version: string;
  generated_at: string;
  provider_used: string;
  summary: string;
  diagnoses: Array<{
    severity: "critical" | "warning" | "optimization";
    target_component: string;
    finding: string;
    recommendation: string;
  }>;
  changes_made: string[];
  proposed_blueprint: AgentArchitecture;
  unified_yaml_diff: string;
}

export interface ABComparisonResponse {
  run_ids: string[];
  runs: RunRecord[];
  winner_run_id?: string | null;
  comparison_matrix: Record<string, Record<string, unknown>>;
  key_takeaways: string[];
}
