import type {
  ABComparisonResponse,
  AdvisorSuggestion,
  AgentArchitecture,
  CompilationResult,
  EvaluationReport,
  HarnessModelsConfig,
  HarnessType,
  RunMode,
  RunRecord,
  TaskSpec,
  TelemetryEvent,
} from "./types";

const API_BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  listBlueprints: () => request<AgentArchitecture[]>("/blueprints"),
  getBlueprint: (id: string) =>
    request<{ blueprint: AgentArchitecture; raw_yaml: string; file_path: string }>(`/blueprints/${id}`),
  saveBlueprint: (payload: {
    blueprint?: AgentArchitecture;
    raw_yaml?: string;
    previous_id?: string;
  }) =>
    request<{ blueprint: AgentArchitecture; raw_yaml: string; file_path: string }>("/blueprints", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteBlueprint: (id: string) =>
    request<{ deleted: boolean; id: string }>(`/blueprints/${id}`, {
      method: "DELETE",
    }),
  convertYaml: (payload: { blueprint?: AgentArchitecture; raw_yaml?: string }) =>
    request<{ blueprint: AgentArchitecture; raw_yaml: string }>("/blueprints/convert-yaml", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  inspectSkillDir: (sourceDir: string) =>
    request<{
      source_dir: string;
      has_skill_md: boolean;
      id: string;
      name: string;
      description: string;
      instructions_preview: string;
      files: string[];
      counts: { references: number; scripts: number; assets: number; resources: number; other: number };
    }>("/blueprints/inspect-skill-dir", {
      method: "POST",
      body: JSON.stringify({ source_dir: sourceDir }),
    }),
  compilePreview: (architectureId: string, harness: HarnessType) =>
    request<CompilationResult>(`/blueprints/${architectureId}/compile/${harness}`),
  compilePreviewInline: (blueprint: AgentArchitecture, harness: HarnessType) =>
    request<CompilationResult>("/blueprints/compile-preview", {
      method: "POST",
      body: JSON.stringify({ blueprint, harness }),
    }),
  exportBlueprint: (
    architectureId: string,
    harness: HarnessType,
    targetDirectory: string,
    taskId?: string,
    docsDirectory?: string
  ) =>
    request<{
      exported: boolean;
      run_id: string;
      target_directory: string;
      docs_directory?: string | null;
      discovered_docs: string[];
      installed_agents: string[];
      installed_commands: string[];
      files_written: string[];
      launch_command: string;
    }>(`/blueprints/${architectureId}/export`, {
      method: "POST",
      body: JSON.stringify({
        harness,
        target_directory: targetDirectory,
        docs_directory: docsDirectory || null,
        task_id: taskId || null,
      }),
    }),
  evaluateDeployedDirectory: (payload: {
    project_directory: string;
    task_id?: string;
    architecture_id?: string;
    harness?: HarnessType;
  }) =>
    request<RunRecord>("/runs/evaluate-directory", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listTasks: () => request<TaskSpec[]>("/tasks"),
  getTask: (id: string) =>
    request<{ task: TaskSpec; raw_yaml: string; file_path: string }>(`/tasks/${id}`),
  saveTask: (payload: { task?: TaskSpec; raw_yaml?: string }) =>
    request<{ task: TaskSpec; raw_yaml: string; file_path: string }>("/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getHarnessStatus: () =>
    request<Record<HarnessType, { available: boolean; binary: string }>>("/runs/harnesses/status"),
  getHarnessModels: () => request<HarnessModelsConfig>("/runs/harnesses/models"),
  updateHarnessModels: (payload: Partial<HarnessModelsConfig>) =>
    request<HarnessModelsConfig>("/runs/harnesses/models", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  syncHarnessModelsFromCli: () =>
    request<HarnessModelsConfig>("/runs/harnesses/models/sync", { method: "POST" }),
  listRuns: () => request<RunRecord[]>("/runs"),
  getRun: (runId: string) => request<RunRecord>(`/runs/${runId}`),
  startRun: (payload: {
    architecture_id: string;
    task_id: string;
    harness: HarnessType;
    mode: RunMode;
    custom_prompt_override?: string;
    auto_evaluate?: boolean;
  }) =>
    request<RunRecord>("/runs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  completeInteractiveRun: (runId: string) =>
    request<RunRecord>(`/runs/${runId}/complete-interactive`, { method: "POST" }),
  stopRun: (runId: string, evaluate = true) =>
    request<RunRecord>(`/runs/${runId}/stop?evaluate=${evaluate}`, { method: "POST" }),
  getTelemetryEvents: (runId: string) => request<TelemetryEvent[]>(`/runs/${runId}/telemetry`),
  getRunLog: (runId: string) => request<{ run_id: string; log: string }>(`/runs/${runId}/log`),
  deleteRun: (runId: string) => request<{ deleted: boolean; id: string }>(`/runs/${runId}`, { method: "DELETE" }),
  deleteAllRuns: () => request<{ deleted_all: boolean; deleted_count: number }>("/runs", { method: "DELETE" }),

  triggerEvaluation: (runId: string) =>
    request<EvaluationReport>(`/evaluations/runs/${runId}/evaluate`, { method: "POST" }),
  saveHumanGrade: (runId: string, rating: number, notes: string) =>
    request<EvaluationReport>(`/evaluations/runs/${runId}/human-grade`, {
      method: "POST",
      body: JSON.stringify({ rating, notes }),
    }),
  compareRuns: (runIds: string[]) =>
    request<ABComparisonResponse>("/evaluations/compare", {
      method: "POST",
      body: JSON.stringify({ run_ids: runIds }),
    }),
  getAdvisorSuggestion: (runId: string, regenerate = false) =>
    request<AdvisorSuggestion>(`/evaluations/runs/${runId}/advisor?regenerate=${regenerate}`),
  applyAdvisorSuggestion: (runId: string, saveAsNewId?: string) =>
    request<AgentArchitecture>(`/evaluations/runs/${runId}/advisor/apply`, {
      method: "POST",
      body: JSON.stringify({ save_as_new_id: saveAsNewId || null }),
    }),
};
