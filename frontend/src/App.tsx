import React, { useEffect, useState, useCallback, useRef } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Bot,
  CheckCircle2,
  Code2,
  Cpu,
  FileCode2,
  FolderOutput,
  GitCompare,
  Layers,
  Loader2,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Save,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Terminal,
  Trash2,
  Wand2,
  XCircle,
} from "lucide-react";
import { api } from "./api";
import { ArchitectureCanvas } from "./components/ArchitectureCanvas";
import type {
  ABComparisonResponse,
  AdvisorSuggestion,
  AgentArchitecture,
  CompilationResult,
  HarnessModelsConfig,
  HarnessType,
  PreflightCheckResponse,
  RunMode,
  RunRecord,
  SubagentSpec,
  TaskSpec,
  TelemetryEvent,
} from "./types";

type ActiveTab = "studio" | "tasks" | "runner" | "evaluation" | "compare" | "advisor";

const HARNESS_LABELS: Record<HarnessType, { name: string; badge: string }> = {
  claude_code: { name: "Claude Code", badge: "CLAUDE.md + .claude/agents" },
  antigravity: { name: "Antigravity (AGY)", badge: ".agent/rules + .agent/agents" },
  opencode: { name: "OpenCode", badge: "AGENTS.md + opencode.json" },
};

export default function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("studio");
  const [blueprints, setBlueprints] = useState<AgentArchitecture[]>([]);
  const [selectedBlueprint, setSelectedBlueprint] = useState<AgentArchitecture | null>(null);
  const [rawYaml, setRawYaml] = useState<string>("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>("root_orchestrator");
  const [studioRightPanel, setStudioRightPanel] = useState<
    "inspector" | "commands" | "yaml" | "compiled" | "models"
  >("inspector");
  const [saveStatus, setSaveStatus] = useState<"saved" | "saving" | "unsaved">("saved");
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const compilePreviewTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Custom Commands form state
  const [newCmdId, setNewCmdId] = useState<string>("");
  const [newCmdDesc, setNewCmdDesc] = useState<string>("");
  const [newCmdPrompt, setNewCmdPrompt] = useState<string>("");
  const [newCmdAgent, setNewCmdAgent] = useState<string>("");
  const [editingCmdId, setEditingCmdId] = useState<string | null>(null);

  const [previewHarness, setPreviewHarness] = useState<HarnessType>("claude_code");
  const [harnessModels, setHarnessModels] = useState<HarnessModelsConfig | null>(null);
  const [newCustomModelId, setNewCustomModelId] = useState<string>("");
  const [newCustomModelLabel, setNewCustomModelLabel] = useState<string>("");
  const [entProvId, setEntProvId] = useState<string>("enterprise-llm");
  const [entProvName, setEntProvName] = useState<string>("Enterprise LLM Gateway");
  const [entProvBaseUrl, setEntProvBaseUrl] = useState<string>("");
  const [entProvApiKeyEnv, setEntProvApiKeyEnv] = useState<string>("ENTERPRISE_LLM_API_KEY");
  const [entProvHeaders, setEntProvHeaders] = useState<string>("");
  const [entProvModelsText, setEntProvModelsText] = useState<string>("");
  const [renamingBlueprintId, setRenamingBlueprintId] = useState<string | null>(null);
  const [renamingBlueprintTitle, setRenamingBlueprintTitle] = useState<string>("");
  const [compiledResult, setCompiledResult] = useState<CompilationResult | null>(null);
  const [selectedCompiledFileIdx, setSelectedCompiledFileIdx] = useState<number>(0);
  const [exportDir, setExportDir] = useState<string>("");
  const [externalDocsDir, setExternalDocsDir] = useState<string>("");
  const [deploymentReceipt, setDeploymentReceipt] = useState<{
    run_id: string;
    target_directory: string;
    docs_directory?: string | null;
    discovered_docs: string[];
    installed_agents: string[];
    installed_commands: string[];
  } | null>(null);
  const [statusBanner, setStatusBanner] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  // Tasks state
  const [tasks, setTasks] = useState<TaskSpec[]>([]);
  const [selectedTask, setSelectedTask] = useState<TaskSpec | null>(null);
  const [taskYaml, setTaskYaml] = useState<string>("");
  const [showNewTaskTemplates, setShowNewTaskTemplates] = useState<boolean>(false);
  const [newVerifierName, setNewVerifierName] = useState<string>("");
  const [newVerifierType, setNewVerifierType] = useState<string>("command_exit_code");
  const [newVerifierCommand, setNewVerifierCommand] = useState<string>("");
  const [newVerifierTargetPath, setNewVerifierTargetPath] = useState<string>("");
  const [newVerifierPattern, setNewVerifierPattern] = useState<string>("");
  const [newVerifierWeight, setNewVerifierWeight] = useState<number>(1.5);
  const [newVerifierRequired, setNewVerifierRequired] = useState<boolean>(true);
  const [newVerifierMaxLines, setNewVerifierMaxLines] = useState<number>(150);
  const [newVerifierTimeout, setNewVerifierTimeout] = useState<number>(60);
  const [editingVerifierId, setEditingVerifierId] = useState<string | null>(null);

  // Runner & Telemetry state
  const [runHarness, setRunHarness] = useState<HarnessType>("claude_code");
  const [runMode, setRunMode] = useState<RunMode>("simulated_benchmark");
  const [harnessStatus, setHarnessStatus] = useState<Record<string, { available: boolean; binary: string }>>({});
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [activeRun, setActiveRun] = useState<RunRecord | null>(null);
  const [telemetryEvents, setTelemetryEvents] = useState<TelemetryEvent[]>([]);
  const [activeAgentNode, setActiveAgentNode] = useState<string | null>(null);
  const [isLaunchingRun, setIsLaunchingRun] = useState(false);
  const [isStoppingRun, setIsStoppingRun] = useState(false);
  const [isClearingStale, setIsClearingStale] = useState(false);
  const [preflight, setPreflight] = useState<PreflightCheckResponse | null>(null);
  const [isCheckingPreflight, setIsCheckingPreflight] = useState(false);
  const [traceViewMode, setTraceViewMode] = useState<"cards" | "console_log">("cards");
  const [plainTextLog, setPlainTextLog] = useState<string>("");
  const runPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isRunStatusActive = (status?: string | null) =>
    status === "preparing_sandbox" || status === "running" || status === "evaluating";

  const isRunStale = (r: RunRecord) =>
    (r.status === "cancelled" || r.status === "failed") && !r.evaluation;

  const runningRun =
    runs.find((r) => isRunStatusActive(r.status)) ||
    (activeRun && isRunStatusActive(activeRun.status) ? activeRun : null);
  const isRunBlocking = isLaunchingRun || Boolean(runningRun);

  // A/B Compare & Advisor state
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [abResult, setAbResult] = useState<ABComparisonResponse | null>(null);
  const [advisorSuggestion, setAdvisorSuggestion] = useState<AdvisorSuggestion | null>(null);
  const [isLoadingAdvisor, setIsLoadingAdvisor] = useState(false);
  const [humanRating, setHumanRating] = useState<number>(5);
  const [humanNotes, setHumanNotes] = useState<string>("");

  const notify = (text: string, type: "ok" | "err" = "ok") => {
    setStatusBanner({ type, text });
    setTimeout(() => setStatusBanner(null), 4500);
  };

  const stopRunPolling = useCallback(() => {
    if (runPollRef.current) {
      clearInterval(runPollRef.current);
      runPollRef.current = null;
    }
  }, []);

  const refreshPreflight = useCallback(async () => {
    if (!selectedBlueprint || !selectedTask) return;
    setIsCheckingPreflight(true);
    try {
      const res = await api.runPreflightChecks({
        architecture_id: selectedBlueprint.metadata.id,
        task_id: selectedTask.id,
        harness: runHarness,
        mode: runMode,
      });
      setPreflight(res);
    } catch {
      // ignore transient errors
    } finally {
      setIsCheckingPreflight(false);
    }
  }, [selectedBlueprint, selectedTask, runHarness, runMode]);

  const startRunPolling = useCallback(
    (runId: string) => {
      stopRunPolling();
      runPollRef.current = setInterval(async () => {
        try {
          const [evts, currentRun, logRes] = await Promise.all([
            api.getTelemetryEvents(runId),
            api.getRun(runId),
            api.getRunLog(runId),
          ]);
          setTelemetryEvents(evts);
          setPlainTextLog(logRes.log);
          if (evts.length > 0) {
            setActiveAgentNode(evts[evts.length - 1].agent_id);
          }
          setActiveRun(currentRun);
          setRuns((prev) => {
            const exists = prev.some((r) => r.id === currentRun.id);
            return exists
              ? prev.map((r) => (r.id === currentRun.id ? currentRun : r))
              : [currentRun, ...prev];
          });
          if (
            currentRun.status === "completed" ||
            currentRun.status === "failed" ||
            currentRun.status === "cancelled" ||
            currentRun.status === "waiting_for_user"
          ) {
            stopRunPolling();
            const allRuns = await api.listRuns();
            setRuns(allRuns);
            if (currentRun.status === "completed") {
              notify(
                `Run ${currentRun.id} completed! Score: ${currentRun.evaluation?.overall_composite_score ?? "--"}/100`
              );
            } else if (currentRun.status === "failed") {
              notify(`Run ${currentRun.id} failed: ${currentRun.error_message || "Unknown error"}`, "err");
            }
          }
        } catch {
          stopRunPolling();
          const allRuns = await api.listRuns().catch(() => null);
          if (allRuns) setRuns(allRuns);
        }
      }, 400);
    },
    [stopRunPolling]
  );

  useEffect(() => {
    return () => stopRunPolling();
  }, [stopRunPolling]);

  const loadInitialData = useCallback(async () => {
    try {
      const [bps, tks, rns, hStatus, hModels, activeStatus] = await Promise.all([
        api.listBlueprints(),
        api.listTasks(),
        api.listRuns(),
        api.getHarnessStatus(),
        api.getHarnessModels(),
        api.getActiveRun().catch(() => ({ has_active_run: false, active_run: null })),
      ]);
      setBlueprints(bps);
      setTasks(tks);
      setRuns(rns);
      setHarnessStatus(hStatus);
      setHarnessModels(hModels);

      if (bps.length > 0) {
        const defaultBp = bps.find((b) => b.metadata.id === "planner-coder-verifier") || bps[0];
        const full = await api.getBlueprint(defaultBp.metadata.id);
        setSelectedBlueprint(full.blueprint);
        setRawYaml(full.raw_yaml);
      }
      if (tks.length > 0) {
        const fullTask = await api.getTask(tks[0].id);
        setSelectedTask(fullTask.task);
        setTaskYaml(fullTask.raw_yaml);
      }
      if (activeStatus.has_active_run && activeStatus.active_run) {
        setActiveRun(activeStatus.active_run);
        startRunPolling(activeStatus.active_run.id);
      } else if (rns.length > 0) {
        setActiveRun(rns[0]);
        setCompareIds(rns.slice(0, 2).map((r) => r.id));
      }
    } catch (err: unknown) {
      notify(err instanceof Error ? err.message : "Failed to connect to backend", "err");
    }
  }, [startRunPolling]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Auto-refresh preflight checks when on Execute & Trace tab or launch configuration changes
  useEffect(() => {
    if (activeTab === "runner" && selectedBlueprint && selectedTask) {
      refreshPreflight();
    }
  }, [activeTab, selectedBlueprint?.metadata.id, selectedTask?.id, runHarness, runMode, runs.length, isRunBlocking, refreshPreflight]);

  // Debounced live compiled preview whenever selected blueprint or target harness changes
  useEffect(() => {
    if (!selectedBlueprint) return;
    if (compilePreviewTimerRef.current) {
      clearTimeout(compilePreviewTimerRef.current);
    }
    compilePreviewTimerRef.current = setTimeout(() => {
      api
        .compilePreviewInline(selectedBlueprint, previewHarness)
        .then((res) => {
          setCompiledResult(res);
          setSelectedCompiledFileIdx((prev) => (prev < res.files.length ? prev : 0));
        })
        .catch(() => { });
    }, 300);
    return () => {
      if (compilePreviewTimerRef.current) {
        clearTimeout(compilePreviewTimerRef.current);
      }
    };
  }, [selectedBlueprint, previewHarness]);

  // Load telemetry events when activeRun changes; auto-prune ghost/stale runs that return 404
  useEffect(() => {
    if (!activeRun) return;
    let cancelled = false;
    api
      .getTelemetryEvents(activeRun.id)
      .then((evts) => {
        if (cancelled) return;
        setTelemetryEvents(evts);
        const lastAgent = [...evts].reverse().find((e) => e.agent_id)?.agent_id || null;
        setActiveAgentNode(lastAgent);
      })
      .catch(() => { });
    api
      .getRunLog(activeRun.id)
      .then((res) => {
        if (!cancelled) setPlainTextLog(res.log);
      })
      .catch(async (err: unknown) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : "";
        if (msg.toLowerCase().includes("not found") || msg.includes("404")) {
          const staleId = activeRun.id;
          const freshRuns = await api.listRuns().catch(() => runs.filter((r) => r.id !== staleId));
          if (cancelled) return;
          setRuns(freshRuns);
          setCompareIds((prev) => prev.filter((id) => id !== staleId));
          const nextRun = freshRuns[0] || null;
          setActiveRun(nextRun);
          if (!nextRun) {
            setTelemetryEvents([]);
            setPlainTextLog("");
          }
          notify(`Removed stale evaluation '${staleId}' (no longer exists on server).`);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeRun?.id]);

  const handleSelectBlueprint = async (id: string) => {
    try {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
        autoSaveTimerRef.current = null;
      }
      const res = await api.getBlueprint(id);
      setSelectedBlueprint(res.blueprint);
      setRawYaml(res.raw_yaml);
      setSelectedNodeId(res.blueprint.orchestrator.id);
      setSaveStatus("saved");
    } catch (err: unknown) {
      notify(err instanceof Error ? err.message : "Error loading blueprint", "err");
    }
  };

  const handleCanvasBlueprintChange = (updated: AgentArchitecture) => {
    setSelectedBlueprint(updated);
    setBlueprints((prev) =>
      prev.map((b) => (b.metadata.id === updated.metadata.id ? updated : b))
    );
    setSaveStatus("saving");

    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
    }
    autoSaveTimerRef.current = setTimeout(async () => {
      try {
        const saved = await api.saveBlueprint({ blueprint: updated });
        setRawYaml(saved.raw_yaml);
        setSaveStatus("saved");
      } catch {
        setSaveStatus("unsaved");
      }
    }, 700);
  };

  const handleSaveBlueprint = async (useRawYaml = false) => {
    try {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
        autoSaveTimerRef.current = null;
      }
      setSaveStatus("saving");
      const payload = useRawYaml ? { raw_yaml: rawYaml } : { blueprint: selectedBlueprint! };
      const saved = await api.saveBlueprint(payload);
      setSelectedBlueprint(saved.blueprint);
      setRawYaml(saved.raw_yaml);
      const bps = await api.listBlueprints();
      setBlueprints(bps);
      const comp = await api.compilePreviewInline(saved.blueprint, previewHarness);
      setCompiledResult(comp);
      setSaveStatus("saved");
      notify(`Saved blueprint '${saved.blueprint.metadata.name}' (v${saved.blueprint.metadata.version})`);
    } catch (err: unknown) {
      setSaveStatus("unsaved");
      notify(err instanceof Error ? err.message : "Failed to save blueprint", "err");
    }
  };

  const handleAddSubagent = () => {
    if (!selectedBlueprint) return;
    const nextIdx = selectedBlueprint.subagents.length + 1;
    const newId = `specialist_${nextIdx}`;
    const newSubagent: SubagentSpec = {
      id: newId,
      name: `Specialist Agent ${nextIdx}`,
      role: "Handles specialized subtask delegated by the orchestrator",
      model: "coding",
      system_prompt: `You are ${newId}. Execute your delegated responsibility cleanly and return a concise summary.`,
      tools: ["read", "write", "edit", "grep", "glob", "bash"],
      permissions: {
        allow_shell: true,
        allow_write: true,
        allow_network: false,
        allowed_commands: [],
        blocked_commands: ["rm -rf /"],
      },
      max_turns: 15,
    };
    const nextOrder = selectedBlueprint.topology.edges.length + 1;
    const updated: AgentArchitecture = {
      ...selectedBlueprint,
      subagents: [...selectedBlueprint.subagents, newSubagent],
      topology: {
        ...selectedBlueprint.topology,
        edges: [
          ...selectedBlueprint.topology.edges,
          {
            id: `e_${newId}`,
            source: selectedBlueprint.orchestrator.id,
            target: newId,
            condition: `Step ${nextOrder}: Delegate to ${newId}`,
            order: nextOrder,
            required: true,
            max_loops: 1,
          },
        ],
      },
      visual_layout: {
        nodes: {
          ...selectedBlueprint.visual_layout.nodes,
          [newId]: { x: 140 + selectedBlueprint.subagents.length * 260, y: 240 },
        },
      },
    };
    handleCanvasBlueprintChange(updated);
    setSelectedNodeId(newId);
  };

  const handleAddGuardrailHook = () => {
    if (!selectedBlueprint) return;
    const newId = `hook_guard_${selectedBlueprint.hooks.length + 1}`;
    const updated: AgentArchitecture = {
      ...selectedBlueprint,
      hooks: [
        ...selectedBlueprint.hooks,
        {
          id: newId,
          event: "PreToolUse",
          matcher: "Write|Edit",
          target_agent: "root_orchestrator",
          action: "block",
          message: "Root orchestrator must delegate code modifications to coding subagents.",
        },
      ],
      visual_layout: {
        nodes: {
          ...selectedBlueprint.visual_layout.nodes,
          [newId]: { x: 680, y: 60 + selectedBlueprint.hooks.length * 140 },
        },
      },
    };
    handleCanvasBlueprintChange(updated);
    setSelectedNodeId(newId);
  };

  const sanitizeSlug = (raw: string) =>
    raw
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "_")
      .replace(/^[_-]+|[_-]+$/g, "");

  const renameAgentId = (kind: "orchestrator" | "subagent", oldId: string, rawNewId: string) => {
    if (!selectedBlueprint) return;
    const candidate = sanitizeSlug(rawNewId);
    if (!candidate || candidate === oldId) return;

    const takenIds = new Set<string>([
      ...(kind === "orchestrator" ? [] : [selectedBlueprint.orchestrator.id]),
      ...selectedBlueprint.subagents
        .filter((s) => !(kind === "subagent" && s.id === oldId))
        .map((s) => s.id),
      ...selectedBlueprint.skills.map((sk) => sk.id),
      ...selectedBlueprint.hooks.map((h) => h.id),
    ]);
    if (takenIds.has(candidate)) {
      notify(`Agent ID '${candidate}' is already in use by another node.`, "err");
      return;
    }

    const nextLayoutNodes = { ...selectedBlueprint.visual_layout.nodes };
    if (nextLayoutNodes[oldId]) {
      nextLayoutNodes[candidate] = nextLayoutNodes[oldId];
      delete nextLayoutNodes[oldId];
    }

    const updated: AgentArchitecture = {
      ...selectedBlueprint,
      orchestrator:
        kind === "orchestrator"
          ? { ...selectedBlueprint.orchestrator, id: candidate }
          : selectedBlueprint.orchestrator,
      subagents:
        kind === "subagent"
          ? selectedBlueprint.subagents.map((s) =>
              s.id === oldId ? { ...s, id: candidate } : s
            )
          : selectedBlueprint.subagents,
      hooks: selectedBlueprint.hooks.map((h) =>
        h.target_agent === oldId ? { ...h, target_agent: candidate } : h
      ),
      commands: (selectedBlueprint.commands || []).map((c) =>
        c.agent === oldId ? { ...c, agent: candidate } : c
      ),
      topology: {
        ...selectedBlueprint.topology,
        entry_node:
          selectedBlueprint.topology.entry_node === oldId
            ? candidate
            : selectedBlueprint.topology.entry_node,
        edges: selectedBlueprint.topology.edges.map((ed) => ({
          ...ed,
          source: ed.source === oldId ? candidate : ed.source,
          target: ed.target === oldId ? candidate : ed.target,
        })),
      },
      visual_layout: { nodes: nextLayoutNodes },
    };

    handleCanvasBlueprintChange(updated);
    setSelectedNodeId(candidate);
    notify(`Renamed ${kind} ID '${oldId}' → '${candidate}'`);
  };

  const renameSkillId = (
    oldId: string,
    rawNewId: string,
    extraPatch?: Partial<AgentArchitecture["skills"][number]>
  ) => {
    if (!selectedBlueprint) return;
    const candidate = sanitizeSlug(rawNewId) || oldId;
    const takenIds = new Set<string>([
      selectedBlueprint.orchestrator.id,
      ...selectedBlueprint.subagents.map((s) => s.id),
      ...selectedBlueprint.hooks.map((h) => h.id),
      ...selectedBlueprint.skills.filter((sk) => sk.id !== oldId).map((sk) => sk.id),
    ]);
    const finalId = takenIds.has(candidate) ? oldId : candidate;

    const nextLayoutNodes = { ...selectedBlueprint.visual_layout.nodes };
    if (finalId !== oldId && nextLayoutNodes[oldId]) {
      nextLayoutNodes[finalId] = nextLayoutNodes[oldId];
      delete nextLayoutNodes[oldId];
    }

    const updated: AgentArchitecture = {
      ...selectedBlueprint,
      skills: selectedBlueprint.skills.map((sk) =>
        sk.id === oldId
          ? {
            ...sk,
            ...extraPatch,
            id: finalId,
            trigger_command: `/${finalId}`,
          }
          : sk
      ),
      topology: {
        ...selectedBlueprint.topology,
        edges: selectedBlueprint.topology.edges.map((ed) => ({
          ...ed,
          source: ed.source === oldId ? finalId : ed.source,
          target: ed.target === oldId ? finalId : ed.target,
        })),
      },
      visual_layout: {
        nodes: nextLayoutNodes,
      },
    };
    handleCanvasBlueprintChange(updated);
    if (finalId !== oldId) {
      setSelectedNodeId(finalId);
    }
  };

  const handleAddSkill = () => {
    if (!selectedBlueprint) return;
    let nextIdx = selectedBlueprint.skills.length + 1;
    const existingIds = new Set(selectedBlueprint.skills.map((s) => s.id));
    while (existingIds.has(`custom-skill-${nextIdx}`)) {
      nextIdx += 1;
    }
    const newId = `custom-skill-${nextIdx}`;
    const updated: AgentArchitecture = {
      ...selectedBlueprint,
      skills: [
        ...selectedBlueprint.skills,
        {
          id: newId,
          name: `Custom Skill ${nextIdx}`,
          description: "Reusable domain skill, workflow, or document template for subagents",
          trigger_command: `/${newId}`,
          instructions: "1. Follow skill workflow.\n2. Include acceptance criteria and validation checks.",
        },
      ],
      visual_layout: {
        nodes: {
          ...selectedBlueprint.visual_layout.nodes,
          [newId]: { x: 180 + selectedBlueprint.skills.length * 260, y: 440 },
        },
      },
    };
    handleCanvasBlueprintChange(updated);
    setSelectedNodeId(newId);
  };

  const handleDuplicateBlueprint = async () => {
    if (!selectedBlueprint) return;
    const customId = `${selectedBlueprint.metadata.id}-custom`;
    const cloned: AgentArchitecture = {
      ...selectedBlueprint,
      metadata: {
        ...selectedBlueprint.metadata,
        id: customId,
        name: `${selectedBlueprint.metadata.name} (Custom)`,
        version: "1.0.0",
      },
    };
    const saved = await api.saveBlueprint({ blueprint: cloned });
    setSelectedBlueprint(saved.blueprint);
    setRawYaml(saved.raw_yaml);
    setBlueprints(await api.listBlueprints());
    notify(`Created editable custom blueprint '${customId}'!`);
  };

  const handleStartRun = async () => {
    if (!selectedBlueprint || !selectedTask) return;
    if (isRunBlocking) {
      notify(
        `An evaluation run (${runningRun?.id || "in progress"}) is already running. Wait for it to finish or stop it first.`,
        "err"
      );
      setActiveTab("runner");
      return;
    }

    setIsLaunchingRun(true);
    try {
      await handleSaveBlueprint(false);

      // Run preliminary pre-flight checks before launching
      const pf = await api.runPreflightChecks({
        architecture_id: selectedBlueprint.metadata.id,
        task_id: selectedTask.id,
        harness: runHarness,
        mode: runMode,
      });
      setPreflight(pf);
      if (!pf.ready) {
        const firstFail = pf.checks.find((c) => c.status === "fail");
        setActiveTab("runner");
        notify(
          `Pre-flight check failed (${firstFail?.name || "Validation"}): ${firstFail?.message || "Resolve blocking issues before running."}`,
          "err"
        );
        return;
      }

      const started = await api.startRun({
        architecture_id: selectedBlueprint.metadata.id,
        task_id: selectedTask.id,
        harness: runHarness,
        mode: runMode,
        auto_evaluate: true,
      });
      setRuns((prev) => [started, ...prev.filter((r) => r.id !== started.id)]);
      setActiveRun(started);
      setActiveTab("runner");
      setTelemetryEvents([]);
      setPlainTextLog("");
      startRunPolling(started.id);
    } catch (err: unknown) {
      notify(err instanceof Error ? err.message : "Failed to start run", "err");
      await refreshPreflight();
    } finally {
      setIsLaunchingRun(false);
    }
  };

  const handleStopActiveRun = async (runId: string) => {
    if (isStoppingRun) return;
    setIsStoppingRun(true);
    try {
      stopRunPolling();
      const stopped = await api.stopRun(runId, true);
      setActiveRun(stopped);
      const allRuns = await api.listRuns();
      setRuns(allRuns);
      notify(`Stopped run ${runId} and evaluated current sandbox outputs`);
      await refreshPreflight();
    } catch (err: unknown) {
      notify(err instanceof Error ? err.message : "Failed to stop run", "err");
    } finally {
      setIsStoppingRun(false);
    }
  };

  const handleClearStaleRuns = async () => {
    if (isRunBlocking || isClearingStale) return;
    setIsClearingStale(true);
    try {
      const res = await api.clearStaleRuns();
      const freshRuns = await api.listRuns();
      setRuns(freshRuns);
      const clearedSet = new Set(res.cleared_run_ids);
      setCompareIds((prev) => prev.filter((id) => !clearedSet.has(id)));
      if (activeRun && (clearedSet.has(activeRun.id) || !freshRuns.some((r) => r.id === activeRun.id))) {
        const nextRun = freshRuns[0] || null;
        setActiveRun(nextRun);
        if (!nextRun) {
          setTelemetryEvents([]);
          setPlainTextLog("");
        }
      }
      if (res.cleared_count > 0 || res.removed_orphan_sandboxes > 0) {
        notify(
          `Cleared ${res.cleared_count} stale evaluation(s)` +
            (res.removed_orphan_sandboxes > 0 ? ` and ${res.removed_orphan_sandboxes} orphaned sandbox folder(s)` : "")
        );
      } else {
        notify("Execution history synced — no stale evaluations found.");
      }
      await refreshPreflight();
    } catch (err: unknown) {
      notify(err instanceof Error ? err.message : "Failed to clear stale evaluations", "err");
    } finally {
      setIsClearingStale(false);
    }
  };

  const handleCompleteInteractive = async () => {
    if (!activeRun) return;
    try {
      const completed = await api.completeInteractiveRun(activeRun.id);
      setActiveRun(completed);
      const allRuns = await api.listRuns();
      setRuns(allRuns);
      notify(`Interactive session evaluated! Composite score: ${completed.evaluation?.overall_composite_score}/100`);
      setActiveTab("evaluation");
    } catch (err: unknown) {
      notify(err instanceof Error ? err.message : "Failed to complete session", "err");
    }
  };

  const handleRunComparison = async () => {
    if (compareIds.length === 0) return;
    try {
      const res = await api.compareRuns(compareIds);
      setAbResult(res);
    } catch (err: unknown) {
      notify(err instanceof Error ? err.message : "Comparison failed", "err");
    }
  };

  const handleLoadAdvisor = async (regenerate = false) => {
    if (!activeRun) return;
    setIsLoadingAdvisor(true);
    try {
      const sug = await api.getAdvisorSuggestion(activeRun.id, regenerate);
      setAdvisorSuggestion(sug);
    } catch (err: unknown) {
      notify(err instanceof Error ? err.message : "Failed to generate advisor suggestion", "err");
    } finally {
      setIsLoadingAdvisor(false);
    }
  };

  const handleApplyAdvisorPatch = async (saveAsNew: boolean) => {
    if (!activeRun || !advisorSuggestion) return;
    try {
      const newId = saveAsNew
        ? `${advisorSuggestion.architecture_id}-v${advisorSuggestion.proposed_version.replace(/\./g, "_")}`
        : undefined;
      const applied = await api.applyAdvisorSuggestion(activeRun.id, newId);
      const bps = await api.listBlueprints();
      setBlueprints(bps);
      await handleSelectBlueprint(applied.metadata.id);
      notify(`Applied AI Advisor v${applied.metadata.version} patch to '${applied.metadata.id}'!`);
      setActiveTab("studio");
    } catch (err: unknown) {
      notify(err instanceof Error ? err.message : "Failed to apply patch", "err");
    }
  };

  // Helper to inspect currently selected node on the canvas
  const selectedSubagent = selectedBlueprint?.subagents.find((s) => s.id === selectedNodeId);
  const selectedSkill = selectedBlueprint?.skills.find((sk) => sk.id === selectedNodeId);
  const selectedHook = selectedBlueprint?.hooks.find((h) => h.id === selectedNodeId);
  const selectedMcpServer = (selectedBlueprint?.mcp_servers || []).find(
    (m) => m.id === selectedNodeId
  );
  const isOrchestratorSelected =
    !selectedNodeId || selectedNodeId === selectedBlueprint?.orchestrator.id;

  const handleAddMcpServer = (assignToAgentId?: string) => {
    if (!selectedBlueprint) return;
    const existing = selectedBlueprint.mcp_servers || [];
    let nextIdx = existing.length + 1;
    const existingIds = new Set(existing.map((m) => m.id));
    while (existingIds.has(`mcp_server_${nextIdx}`)) {
      nextIdx += 1;
    }
    const newId = `mcp_server_${nextIdx}`;
    const newServer = {
      id: newId,
      description: "Custom MCP server exposing external tools or data",
      transport: "stdio" as const,
      command: "npx",
      args: ["-y", "@modelcontextprotocol/server-filesystem", "."],
      url: null,
      env: {},
    };
    const updated: AgentArchitecture = {
      ...selectedBlueprint,
      mcp_servers: [...existing, newServer],
      orchestrator:
        assignToAgentId === selectedBlueprint.orchestrator.id
          ? {
              ...selectedBlueprint.orchestrator,
              mcp_servers: [...(selectedBlueprint.orchestrator.mcp_servers || []), newId],
            }
          : selectedBlueprint.orchestrator,
      subagents: selectedBlueprint.subagents.map((sa) =>
        assignToAgentId === sa.id
          ? { ...sa, mcp_servers: [...(sa.mcp_servers || []), newId] }
          : sa
      ),
      visual_layout: {
        nodes: {
          ...selectedBlueprint.visual_layout.nodes,
          [newId]: { x: 680, y: 300 + existing.length * 130 },
        },
      },
    };
    handleCanvasBlueprintChange(updated);
    setSelectedNodeId(newId);
    notify(
      assignToAgentId
        ? `Added MCP server '${newId}' and assigned it to '${assignToAgentId}'`
        : `Added MCP server '${newId}'`
    );
  };

  const toggleAgentMcpServer = (
    kind: "orchestrator" | "subagent",
    agentId: string,
    mcpId: string
  ) => {
    if (!selectedBlueprint) return;
    if (kind === "orchestrator") {
      const curr = selectedBlueprint.orchestrator.mcp_servers || [];
      const next = curr.includes(mcpId)
        ? curr.filter((m) => m !== mcpId)
        : [...curr, mcpId];
      handleCanvasBlueprintChange({
        ...selectedBlueprint,
        orchestrator: { ...selectedBlueprint.orchestrator, mcp_servers: next },
      });
    } else {
      handleCanvasBlueprintChange({
        ...selectedBlueprint,
        subagents: selectedBlueprint.subagents.map((sa) => {
          if (sa.id !== agentId) return sa;
          const curr = sa.mcp_servers || [];
          const next = curr.includes(mcpId)
            ? curr.filter((m) => m !== mcpId)
            : [...curr, mcpId];
          return { ...sa, mcp_servers: next };
        }),
      });
    }
  };

  const renameMcpServerId = (oldId: string, rawNewId: string) => {
    if (!selectedBlueprint) return;
    const candidate = sanitizeSlug(rawNewId);
    if (!candidate || candidate === oldId) return;
    const existing = selectedBlueprint.mcp_servers || [];
    if (existing.some((m) => m.id === candidate)) {
      notify(`MCP server ID '${candidate}' already exists.`, "err");
      return;
    }
    const nextLayout = { ...selectedBlueprint.visual_layout.nodes };
    if (nextLayout[oldId]) {
      nextLayout[candidate] = nextLayout[oldId];
      delete nextLayout[oldId];
    }
    handleCanvasBlueprintChange({
      ...selectedBlueprint,
      mcp_servers: existing.map((m) => (m.id === oldId ? { ...m, id: candidate } : m)),
      orchestrator: {
        ...selectedBlueprint.orchestrator,
        mcp_servers: (selectedBlueprint.orchestrator.mcp_servers || []).map((m) =>
          m === oldId ? candidate : m
        ),
      },
      subagents: selectedBlueprint.subagents.map((sa) => ({
        ...sa,
        mcp_servers: (sa.mcp_servers || []).map((m) => (m === oldId ? candidate : m)),
      })),
      visual_layout: { nodes: nextLayout },
    });
    setSelectedNodeId(candidate);
    notify(`Renamed MCP server '${oldId}' → '${candidate}'`);
  };

  const deleteMcpServer = (mcpId: string) => {
    if (!selectedBlueprint) return;
    const nextLayout = { ...selectedBlueprint.visual_layout.nodes };
    delete nextLayout[mcpId];
    handleCanvasBlueprintChange({
      ...selectedBlueprint,
      mcp_servers: (selectedBlueprint.mcp_servers || []).filter((m) => m.id !== mcpId),
      orchestrator: {
        ...selectedBlueprint.orchestrator,
        mcp_servers: (selectedBlueprint.orchestrator.mcp_servers || []).filter((m) => m !== mcpId),
      },
      subagents: selectedBlueprint.subagents.map((sa) => ({
        ...sa,
        mcp_servers: (sa.mcp_servers || []).filter((m) => m !== mcpId),
      })),
      visual_layout: { nodes: nextLayout },
    });
    if (selectedNodeId === mcpId) {
      setSelectedNodeId(selectedBlueprint.orchestrator.id);
    }
    notify(`Deleted MCP server '${mcpId}'`);
  };

  return (
    <div className="min-h-screen h-screen flex flex-col bg-slate-950 text-slate-100 overflow-hidden">
      {/* Top Navigation Bar */}
      <header className="h-14 border-b border-slate-800 bg-slate-900/90 px-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center shadow-md shadow-indigo-500/20">
            <Cpu className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-base tracking-tight text-white">HarnessForge</span>
              <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                Multi-Harness Studio
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Design, Deploy & Benchmark Agentic Architectures for Claude Code, Antigravity & OpenCode
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
          {[
            { id: "studio", label: "1. Architecture Studio", icon: Layers },
            { id: "tasks", label: "2. Benchmark Tasks", icon: FileCode2 },
            { id: "runner", label: "3. Execute & Trace", icon: Play },
            { id: "evaluation", label: "4. Evaluation Scorecard", icon: BarChart3 },
            { id: "compare", label: "5. A/B Matrix", icon: GitCompare },
            { id: "advisor", label: "6. AI Advisor (v2 Diff)", icon: Wand2 },
          ].map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id as ActiveTab);
                  if (tab.id === "compare") handleRunComparison();
                  if (tab.id === "advisor" && activeRun) handleLoadAdvisor(false);
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${active
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
                  }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            );
          })}
        </nav>

        {/* Quick Run Toolbar */}
        <div className="flex items-center gap-2">
          <select
            value={runHarness}
            onChange={(e) => {
              const nextH = e.target.value as HarnessType;
              setRunHarness(nextH);
              setPreviewHarness(nextH);
            }}
            className="bg-slate-950 border border-indigo-500/70 rounded-lg px-2.5 py-1.5 text-xs text-cyan-300 font-semibold"
          >
            <option value="claude_code">Target: Claude Code</option>
            <option value="antigravity">Target: Antigravity (AGY)</option>
            <option value="opencode">Target: OpenCode</option>
          </select>
          <button
            onClick={handleStartRun}
            disabled={isRunBlocking || !selectedBlueprint || !selectedTask}
            title={
              isRunBlocking
                ? `Blocked: run ${runningRun?.id || ""} is currently in progress`
                : "Run pre-flight checks, deploy to sandbox, and evaluate"
            }
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-xs shadow-sm cursor-pointer"
          >
            {isRunBlocking ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5 fill-current" />
            )}
            {isLaunchingRun
              ? "Running Pre-Flight..."
              : runningRun
                ? runningRun.status === "evaluating"
                  ? "Evaluating..."
                  : "Evaluation Running..."
                : "Deploy & Evaluate"}
          </button>
        </div>
      </header>

      {/* Notification Banner */}
      {statusBanner && (
        <div
          className={`px-4 py-2 text-xs font-medium flex items-center justify-between border-b ${statusBanner.type === "ok"
            ? "bg-emerald-950/90 text-emerald-200 border-emerald-800"
            : "bg-rose-950/90 text-rose-200 border-rose-800"
            }`}
        >
          <span>{statusBanner.text}</span>
          <button onClick={() => setStatusBanner(null)} className="text-slate-400 hover:text-white">
            ✕
          </button>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 flex overflow-hidden">
        {/* ==================== TAB 1: ARCHITECTURE STUDIO ==================== */}
        {activeTab === "studio" && selectedBlueprint && (
          <div className="flex-1 flex overflow-hidden">
            {/* Left Sidebar: Blueprint Presets & Palette */}
            <aside className="w-72 border-r border-slate-800 bg-slate-900/60 flex flex-col shrink-0">
              <div className="p-3.5 border-b border-slate-800 max-h-[48%] overflow-y-auto">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Architecture Blueprints ({blueprints.length})
                  </div>
                  <button
                    onClick={handleDuplicateBlueprint}
                    className="flex items-center gap-1 px-2 py-0.5 rounded bg-indigo-950/80 hover:bg-indigo-900 border border-indigo-700/60 text-indigo-300 text-[10px] font-semibold cursor-pointer"
                    title="Clone selected blueprint as a new custom architecture"
                  >
                    <Plus className="w-3 h-3" /> New / Clone
                  </button>
                </div>
                <div className="space-y-1.5">
                  {blueprints.map((bp) => {
                    const isSel = bp.metadata.id === selectedBlueprint.metadata.id;
                    const isRenaming = renamingBlueprintId === bp.metadata.id;
                    return (
                      <div
                        key={bp.metadata.id}
                        onClick={() => handleSelectBlueprint(bp.metadata.id)}
                        className={`w-full text-left p-2.5 rounded-xl border transition-all cursor-pointer group ${isSel
                          ? "bg-indigo-950/70 border-indigo-500/80 text-white"
                          : "bg-slate-900/80 border-slate-800 text-slate-300 hover:border-slate-700"
                          }`}
                      >
                        {isRenaming ? (
                          <div
                            className="flex items-center gap-1"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <input
                              autoFocus
                              value={renamingBlueprintTitle}
                              onChange={(e) => setRenamingBlueprintTitle(e.target.value)}
                              onKeyDown={async (e) => {
                                if (e.key === "Enter" && renamingBlueprintTitle.trim()) {
                                  const full = await api.getBlueprint(bp.metadata.id);
                                  const updatedBp: AgentArchitecture = {
                                    ...full.blueprint,
                                    metadata: {
                                      ...full.blueprint.metadata,
                                      name: renamingBlueprintTitle.trim(),
                                    },
                                  };
                                  const saved = await api.saveBlueprint({ blueprint: updatedBp });
                                  if (isSel) {
                                    setSelectedBlueprint(saved.blueprint);
                                    setRawYaml(saved.raw_yaml);
                                  }
                                  setBlueprints(await api.listBlueprints());
                                  setRenamingBlueprintId(null);
                                  notify(`Renamed blueprint to '${saved.blueprint.metadata.name}'`);
                                } else if (e.key === "Escape") {
                                  setRenamingBlueprintId(null);
                                }
                              }}
                              className="flex-1 bg-slate-950 border border-indigo-500 rounded px-2 py-1 text-xs text-white focus:outline-none"
                            />
                            <button
                              onClick={async () => {
                                if (!renamingBlueprintTitle.trim()) {
                                  setRenamingBlueprintId(null);
                                  return;
                                }
                                const full = await api.getBlueprint(bp.metadata.id);
                                const updatedBp: AgentArchitecture = {
                                  ...full.blueprint,
                                  metadata: {
                                    ...full.blueprint.metadata,
                                    name: renamingBlueprintTitle.trim(),
                                  },
                                };
                                const saved = await api.saveBlueprint({ blueprint: updatedBp });
                                if (isSel) {
                                  setSelectedBlueprint(saved.blueprint);
                                  setRawYaml(saved.raw_yaml);
                                }
                                setBlueprints(await api.listBlueprints());
                                setRenamingBlueprintId(null);
                                notify(`Renamed blueprint to '${saved.blueprint.metadata.name}'`);
                              }}
                              className="px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-bold cursor-pointer"
                            >
                              Save
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center justify-between gap-1.5">
                            <span className="font-semibold text-xs truncate">
                              {bp.metadata.name}
                            </span>
                            <div className="flex items-center gap-1 shrink-0">
                              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-indigo-300">
                                v{bp.metadata.version}
                              </span>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setRenamingBlueprintId(bp.metadata.id);
                                  setRenamingBlueprintTitle(bp.metadata.name);
                                }}
                                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-300 transition-colors cursor-pointer"
                                title={`Rename '${bp.metadata.name}'`}
                              >
                                <Pencil className="w-3 h-3" />
                              </button>
                              <button
                                onClick={async (e) => {
                                  e.stopPropagation();
                                  if (blueprints.length <= 1) {
                                    notify("Cannot delete the last remaining architecture blueprint", "err");
                                    return;
                                  }
                                  try {
                                    await api.deleteBlueprint(bp.metadata.id);
                                    const remaining = await api.listBlueprints();
                                    setBlueprints(remaining);
                                    if (isSel && remaining.length > 0) {
                                      await handleSelectBlueprint(remaining[0].metadata.id);
                                    }
                                    notify(`Deleted architecture blueprint '${bp.metadata.name}'`);
                                  } catch (err: unknown) {
                                    notify(
                                      err instanceof Error ? err.message : "Failed to delete blueprint",
                                      "err"
                                    );
                                  }
                                }}
                                className="p-1 rounded hover:bg-rose-950 text-slate-400 hover:text-rose-400 transition-colors cursor-pointer"
                                title={`Delete '${bp.metadata.name}'`}
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </div>
                          </div>
                        )}
                        <div className="flex items-center gap-2 mt-1.5 text-[10px] text-slate-400">
                          <span>{bp.topology.pattern}</span>
                          <span>•</span>
                          <span>{bp.subagents.length} subagents</span>
                          <span>•</span>
                          <span>{bp.hooks.length} hooks</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Add Primitives Palette */}
              <div className="p-3.5 border-b border-slate-800 space-y-2">
                <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Add Harness Primitives
                </div>
                <button
                  onClick={handleAddSubagent}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-cyan-950/60 hover:bg-cyan-900/60 border border-cyan-700/50 text-cyan-200 text-xs font-medium cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Subagent Node
                </button>
                <button
                  onClick={handleAddSkill}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-950/60 hover:bg-emerald-900/60 border border-emerald-700/50 text-emerald-200 text-xs font-medium cursor-pointer"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  Add Skill / Doc Template
                </button>
                <button
                  onClick={handleAddGuardrailHook}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-950/60 hover:bg-amber-900/60 border border-amber-700/50 text-amber-200 text-xs font-medium cursor-pointer"
                >
                  <ShieldAlert className="w-3.5 h-3.5" />
                  Add Lifecycle Guardrail Hook
                </button>
                <button
                  onClick={() => handleAddMcpServer()}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-purple-950/60 hover:bg-purple-900/60 border border-purple-700/50 text-purple-200 text-xs font-medium cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add MCP Server Node
                </button>
                <button
                  onClick={handleDuplicateBlueprint}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-medium cursor-pointer"
                >
                  <Layers className="w-3.5 h-3.5" />
                  Clone as My Custom Blueprint
                </button>
              </div>

              {/* Topology Pattern & Enforcement Mode */}
              <div className="p-3.5 space-y-3 overflow-y-auto flex-1">
                <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Topology & Enforcement
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Topology Pattern</label>
                  <select
                    value={selectedBlueprint.topology.pattern}
                    onChange={(e) =>
                      handleCanvasBlueprintChange({
                        ...selectedBlueprint,
                        topology: {
                          ...selectedBlueprint.topology,
                          pattern: e.target.value as AgentArchitecture["topology"]["pattern"],
                        },
                      })
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs"
                  >
                    <option value="solo">solo (Single Agent)</option>
                    <option value="sequential-pipeline">sequential-pipeline</option>
                    <option value="generator-verifier-loop">generator-verifier-loop (Actor-Critic)</option>
                    <option value="parallel-swarm">parallel-swarm</option>
                    <option value="router-dispatcher">router-dispatcher</option>
                    <option value="hierarchical-custom">hierarchical-custom</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">
                    Dual-Mode Compilation Guard
                  </label>
                  <select
                    value={selectedBlueprint.topology.enforcement_mode}
                    onChange={(e) =>
                      handleCanvasBlueprintChange({
                        ...selectedBlueprint,
                        topology: {
                          ...selectedBlueprint.topology,
                          enforcement_mode: e.target.value as "prompt" | "hook" | "dual",
                        },
                      })
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs"
                  >
                    <option value="dual">Dual (Prompt Contract + State-Machine Hooks)</option>
                    <option value="prompt">Prompt Routing Contract Only</option>
                    <option value="hook">Runtime Hook State-Machine Only</option>
                  </select>
                </div>

                <div className="pt-2">
                  <button
                    onClick={() => handleSaveBlueprint(false)}
                    className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs cursor-pointer"
                  >
                    <Save className="w-3.5 h-3.5" />
                    Save Blueprint to Disk (.yaml)
                  </button>
                </div>
              </div>
            </aside>

            {/* Center: Interactive React Flow Canvas */}
            <div className="flex-1 flex flex-col relative">
              <div className="h-11 border-b border-slate-800 bg-slate-900/50 px-4 flex items-center justify-between text-xs gap-4">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <span className="text-[11px] text-slate-400 shrink-0">Blueprint Name:</span>
                  <input
                    value={selectedBlueprint.metadata.name}
                    onChange={(e) =>
                      handleCanvasBlueprintChange({
                        ...selectedBlueprint,
                        metadata: { ...selectedBlueprint.metadata, name: e.target.value },
                      })
                    }
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleSaveBlueprint(false);
                    }}
                    className="bg-slate-950/90 border border-slate-700 hover:border-indigo-500/70 focus:border-indigo-500 rounded-lg px-2.5 py-1 text-xs font-semibold text-white w-80 max-w-full focus:outline-none"
                    title="Click to edit Architecture Blueprint Name (press Enter or click Save Blueprint)"
                  />
                  <input
                    value={selectedBlueprint.metadata.version}
                    onChange={(e) =>
                      handleCanvasBlueprintChange({
                        ...selectedBlueprint,
                        metadata: { ...selectedBlueprint.metadata, version: e.target.value },
                      })
                    }
                    className="bg-slate-950/90 border border-slate-800 rounded-lg px-2 py-1 text-[11px] font-mono text-indigo-300 w-16 text-center focus:outline-none"
                    title="Blueprint semantic version"
                  />
                  <button
                    onClick={() => handleSaveBlueprint(false)}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-indigo-600/80 hover:bg-indigo-500 text-white text-[11px] font-semibold cursor-pointer shrink-0"
                  >
                    <Save className="w-3 h-3" /> Save
                  </button>
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded shrink-0 ${
                      saveStatus === "saved"
                        ? "bg-emerald-950/70 text-emerald-300 border border-emerald-800/60"
                        : saveStatus === "saving"
                        ? "bg-amber-950/70 text-amber-300 border border-amber-800/60"
                        : "bg-rose-950/70 text-rose-300 border border-rose-800/60"
                    }`}
                  >
                    {saveStatus === "saved" ? "Auto-Saved ✓" : saveStatus === "saving" ? "Saving..." : "Unsaved"}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[11px] text-slate-400 shrink-0">
                  <span className="inline-block w-2.5 h-2.5 rounded-full bg-indigo-500" /> Orchestrator
                  <span className="inline-block w-2.5 h-2.5 rounded-full bg-cyan-500 ml-2" /> Subagent
                  <span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500 ml-2" /> Skill
                  <span className="inline-block w-2.5 h-2.5 rounded-full bg-amber-500 ml-2" /> Hook
                  <span className="inline-block w-2.5 h-2.5 rounded-full bg-purple-500 ml-2" /> MCP
                </div>
              </div>
              <div className="flex-1">
                <ArchitectureCanvas
                  blueprint={selectedBlueprint}
                  targetHarness={runHarness}
                  harnessModels={harnessModels}
                  activeAgentId={activeAgentNode}
                  selectedNodeId={selectedNodeId}
                  onSelectNode={setSelectedNodeId}
                  onUpdateBlueprint={handleCanvasBlueprintChange}
                />
              </div>
            </div>

            {/* Right Panel: Node Inspector / Commands / Harness Models / YAML / Compiled Files */}
            <aside className="w-[480px] border-l border-slate-800 bg-slate-900/70 flex flex-col shrink-0">
              <div className="flex border-b border-slate-800 bg-slate-950/60">
                {[
                  { id: "inspector", label: "Inspector", icon: Bot },
                  { id: "commands", label: `Commands (${(selectedBlueprint.commands || []).length})`, icon: Sparkles },
                  { id: "models", label: "Models", icon: Cpu },
                  { id: "yaml", label: "YAML", icon: Code2 },
                  { id: "compiled", label: "Compiled", icon: Terminal },
                ].map((p) => {
                  const Icon = p.icon;
                  return (
                    <button
                      key={p.id}
                      onClick={() => setStudioRightPanel(p.id as typeof studioRightPanel)}
                      className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium border-b-2 transition-all cursor-pointer ${studioRightPanel === p.id
                        ? "border-indigo-500 text-white bg-slate-900"
                        : "border-transparent text-slate-400 hover:text-slate-200"
                        }`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      {p.label}
                    </button>
                  );
                })}
              </div>

              {/* Panel 1: Node & Edge Inspector */}
              {studioRightPanel === "inspector" && (
                <div className="p-4 overflow-y-auto flex-1 space-y-4 text-xs">
                  {isOrchestratorSelected && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-wider text-indigo-400">
                          Root Orchestrator Config
                        </span>
                        <span className="font-mono text-[11px] text-slate-400">
                          {selectedBlueprint.orchestrator.id}
                        </span>
                      </div>
                      <div>
                        <label className="block text-slate-400 mb-1">
                          Agent ID / Slug <span className="text-[10px] text-slate-500">(Press Enter or blur to rename)</span>
                        </label>
                        <input
                          key={`orch-id-${selectedBlueprint.orchestrator.id}`}
                          defaultValue={selectedBlueprint.orchestrator.id}
                          onBlur={(e) => {
                            if (e.target.value.trim() && e.target.value.trim() !== selectedBlueprint.orchestrator.id) {
                              renameAgentId("orchestrator", selectedBlueprint.orchestrator.id, e.target.value);
                            }
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              const val = (e.target as HTMLInputElement).value;
                              if (val.trim() && val.trim() !== selectedBlueprint.orchestrator.id) {
                                renameAgentId("orchestrator", selectedBlueprint.orchestrator.id, val);
                              }
                            }
                          }}
                          placeholder="e.g. pm_meeting_orchestrator"
                          className="w-full bg-slate-950 border border-indigo-700/60 rounded-lg px-2.5 py-1.5 font-mono text-indigo-300"
                        />
                      </div>
                      <div>
                        <label className="block text-slate-400 mb-1">Display Name</label>
                        <input
                          value={selectedBlueprint.orchestrator.name}
                          onChange={(e) =>
                            handleCanvasBlueprintChange({
                              ...selectedBlueprint,
                              orchestrator: { ...selectedBlueprint.orchestrator, name: e.target.value },
                            })
                          }
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5"
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-slate-400 mb-1">
                            Model Tier ({HARNESS_LABELS[runHarness].name})
                          </label>
                          <select
                            value={selectedBlueprint.orchestrator.model}
                            onChange={(e) =>
                              handleCanvasBlueprintChange({
                                ...selectedBlueprint,
                                orchestrator: { ...selectedBlueprint.orchestrator, model: e.target.value },
                              })
                            }
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-cyan-300 font-mono text-[11px]"
                          >
                            <optgroup label={`Abstract Tiers (${HARNESS_LABELS[runHarness].name} Mapping)`}>
                              {(["default", "reasoning", "coding", "fast"] as const).map((tier) => (
                                <option key={tier} value={tier}>
                                  {tier} → {harnessModels?.tier_map?.[runHarness]?.[tier] || tier}
                                </option>
                              ))}
                            </optgroup>
                            <optgroup label={`Native ${HARNESS_LABELS[runHarness].name} Models`}>
                              {(harnessModels?.native_models?.[runHarness] || []).map((m) => (
                                <option key={m.id} value={m.id}>
                                  {m.label}
                                </option>
                              ))}
                            </optgroup>
                          </select>
                        </div>
                        <div>
                          <label className="block text-slate-400 mb-1">Max Turns Budget</label>
                          <input
                            type="number"
                            value={selectedBlueprint.orchestrator.budgets.max_turns}
                            onChange={(e) =>
                              handleCanvasBlueprintChange({
                                ...selectedBlueprint,
                                orchestrator: {
                                  ...selectedBlueprint.orchestrator,
                                  budgets: {
                                    ...selectedBlueprint.orchestrator.budgets,
                                    max_turns: Number(e.target.value) || 20,
                                  },
                                },
                              })
                            }
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5"
                          />
                        </div>
                      </div>

                      {/* Per-Harness Explicit Model Overrides for Orchestrator */}
                      <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-bold text-indigo-300">
                            Per-Harness Model Pinning (Root Orchestrator)
                          </span>
                          <span className="text-[10px] text-slate-500">Optional overrides for A/B benchmarks</span>
                        </div>
                        <div className="grid grid-cols-3 gap-1.5">
                          {(["claude_code", "antigravity", "opencode"] as HarnessType[]).map((h) => (
                            <div key={h}>
                              <label className="block text-[10px] text-slate-400 mb-0.5">
                                {HARNESS_LABELS[h].name}
                              </label>
                              <select
                                value={selectedBlueprint.orchestrator.harness_models?.[h] || ""}
                                onChange={(e) => {
                                  const nextMap = {
                                    ...(selectedBlueprint.orchestrator.harness_models || {}),
                                  };
                                  if (e.target.value) nextMap[h] = e.target.value;
                                  else delete nextMap[h];
                                  handleCanvasBlueprintChange({
                                    ...selectedBlueprint,
                                    orchestrator: {
                                      ...selectedBlueprint.orchestrator,
                                      harness_models: nextMap,
                                    },
                                  });
                                }}
                                className={`w-full bg-slate-900 border rounded px-1.5 py-1 text-[10px] font-mono ${runHarness === h
                                  ? "border-cyan-500/70 text-cyan-200"
                                  : "border-slate-800 text-slate-300"
                                  }`}
                              >
                                <option value="">
                                  Tier Default (
                                  {harnessModels?.tier_map?.[h]?.[selectedBlueprint.orchestrator.model] ||
                                    selectedBlueprint.orchestrator.model}
                                  )
                                </option>
                                {(harnessModels?.native_models?.[h] || []).map((m) => (
                                  <option key={m.id} value={m.id}>
                                    {m.id}
                                  </option>
                                ))}
                              </select>
                            </div>
                          ))}
                        </div>
                        <div className="text-[10px] text-slate-400 leading-relaxed pt-1 border-t border-slate-800/80">
                          💡 {harnessModels?.best_practices?.orchestrator}
                        </div>
                      </div>
                      <div className="flex items-center gap-4 pt-1">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={selectedBlueprint.orchestrator.permissions.allow_write}
                            onChange={(e) =>
                              handleCanvasBlueprintChange({
                                ...selectedBlueprint,
                                orchestrator: {
                                  ...selectedBlueprint.orchestrator,
                                  permissions: {
                                    ...selectedBlueprint.orchestrator.permissions,
                                    allow_write: e.target.checked,
                                  },
                                },
                              })
                            }
                          />
                          <span>Allow Direct File Write</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={selectedBlueprint.orchestrator.permissions.allow_shell}
                            onChange={(e) =>
                              handleCanvasBlueprintChange({
                                ...selectedBlueprint,
                                orchestrator: {
                                  ...selectedBlueprint.orchestrator,
                                  permissions: {
                                    ...selectedBlueprint.orchestrator.permissions,
                                    allow_shell: e.target.checked,
                                  },
                                },
                              })
                            }
                          />
                          <span>Allow Direct Shell</span>
                        </label>
                      </div>
                      <div>
                        <label className="block text-slate-400 mb-1">System Prompt</label>
                        <textarea
                          rows={6}
                          value={selectedBlueprint.orchestrator.system_prompt}
                          onChange={(e) =>
                            handleCanvasBlueprintChange({
                              ...selectedBlueprint,
                              orchestrator: {
                                ...selectedBlueprint.orchestrator,
                                system_prompt: e.target.value,
                              },
                            })
                          }
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 font-mono text-[11px] leading-relaxed"
                        />
                      </div>

                      {/* Assigned MCP Servers (CRUD & Assign from Root Orchestrator) */}
                      <div className="p-2.5 rounded-xl bg-slate-950 border border-purple-800/50 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-purple-300">
                            Connected MCP Servers ({(selectedBlueprint.orchestrator.mcp_servers || []).length}/{(selectedBlueprint.mcp_servers || []).length})
                          </span>
                          <button
                            onClick={() => handleAddMcpServer(selectedBlueprint.orchestrator.id)}
                            className="px-2 py-0.5 rounded bg-purple-700 hover:bg-purple-600 text-white text-[10px] font-semibold cursor-pointer"
                          >
                            + Add &amp; Assign MCP
                          </button>
                        </div>
                        {(selectedBlueprint.mcp_servers || []).length === 0 ? (
                          <div className="text-[10px] text-slate-400">
                            No MCP servers in this blueprint yet. Click <strong>+ Add &amp; Assign MCP</strong> to connect one.
                          </div>
                        ) : (
                          <div className="space-y-1">
                            {(selectedBlueprint.mcp_servers || []).map((srv) => {
                              const assigned = (selectedBlueprint.orchestrator.mcp_servers || []).includes(srv.id);
                              return (
                                <div key={srv.id} className="flex items-center justify-between gap-2 px-2 py-1 rounded bg-slate-900 border border-slate-800">
                                  <label className="flex items-center gap-2 cursor-pointer min-w-0 flex-1">
                                    <input
                                      type="checkbox"
                                      checked={assigned}
                                      onChange={() => toggleAgentMcpServer("orchestrator", selectedBlueprint.orchestrator.id, srv.id)}
                                    />
                                    <span className="font-mono text-[11px] text-purple-300 truncate">{srv.id}</span>
                                    <span className="text-[9px] text-slate-400 uppercase">{srv.transport}</span>
                                  </label>
                                  <div className="flex items-center gap-1 shrink-0">
                                    <button
                                      onClick={() => setSelectedNodeId(srv.id)}
                                      className="p-0.5 text-slate-400 hover:text-purple-300 cursor-pointer"
                                      title={`Edit MCP server '${srv.id}'`}
                                    >
                                      <Pencil className="w-3 h-3" />
                                    </button>
                                    <button
                                      onClick={() => deleteMcpServer(srv.id)}
                                      className="p-0.5 text-slate-500 hover:text-rose-400 cursor-pointer"
                                      title={`Delete MCP server '${srv.id}'`}
                                    >
                                      <Trash2 className="w-3 h-3" />
                                    </button>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {selectedSubagent && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">
                          Subagent Node: {selectedSubagent.id}
                        </span>
                        <button
                          onClick={() => {
                            const updated: AgentArchitecture = {
                              ...selectedBlueprint,
                              subagents: selectedBlueprint.subagents.filter(
                                (s) => s.id !== selectedSubagent.id
                              ),
                              topology: {
                                ...selectedBlueprint.topology,
                                edges: selectedBlueprint.topology.edges.filter(
                                  (e) =>
                                    e.source !== selectedSubagent.id && e.target !== selectedSubagent.id
                                ),
                              },
                            };
                            handleCanvasBlueprintChange(updated);
                            setSelectedNodeId(selectedBlueprint.orchestrator.id);
                          }}
                          className="text-rose-400 hover:text-rose-300 flex items-center gap-1 text-[11px] cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" /> Remove
                        </button>
                      </div>
                      <div>
                        <label className="block text-slate-400 mb-1">
                          Subagent ID / Slug <span className="text-[10px] text-slate-500">(Press Enter or blur to rename)</span>
                        </label>
                        <input
                          key={`sa-id-${selectedSubagent.id}`}
                          defaultValue={selectedSubagent.id}
                          onBlur={(e) => {
                            if (e.target.value.trim() && e.target.value.trim() !== selectedSubagent.id) {
                              renameAgentId("subagent", selectedSubagent.id, e.target.value);
                            }
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              const val = (e.target as HTMLInputElement).value;
                              if (val.trim() && val.trim() !== selectedSubagent.id) {
                                renameAgentId("subagent", selectedSubagent.id, val);
                              }
                            }
                          }}
                          placeholder="e.g. requirements_elicitor"
                          className="w-full bg-slate-950 border border-cyan-700/60 rounded-lg px-2.5 py-1.5 font-mono text-cyan-300"
                        />
                      </div>
                      <div>
                        <label className="block text-slate-400 mb-1">Subagent Name</label>
                        <input
                          value={selectedSubagent.name}
                          onChange={(e) =>
                            handleCanvasBlueprintChange({
                              ...selectedBlueprint,
                              subagents: selectedBlueprint.subagents.map((s) =>
                                s.id === selectedSubagent.id ? { ...s, name: e.target.value } : s
                              ),
                            })
                          }
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5"
                        />
                      </div>
                      <div>
                        <label className="block text-slate-400 mb-1">
                          Role Description (Used by Orchestrator Router)
                        </label>
                        <input
                          value={selectedSubagent.role}
                          onChange={(e) =>
                            handleCanvasBlueprintChange({
                              ...selectedBlueprint,
                              subagents: selectedBlueprint.subagents.map((s) =>
                                s.id === selectedSubagent.id ? { ...s, role: e.target.value } : s
                              ),
                            })
                          }
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5"
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-slate-400 mb-1">
                            Model Tier ({HARNESS_LABELS[runHarness].name})
                          </label>
                          <select
                            value={selectedSubagent.model}
                            onChange={(e) =>
                              handleCanvasBlueprintChange({
                                ...selectedBlueprint,
                                subagents: selectedBlueprint.subagents.map((s) =>
                                  s.id === selectedSubagent.id ? { ...s, model: e.target.value } : s
                                ),
                              })
                            }
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-cyan-300 font-mono text-[11px]"
                          >
                            <optgroup label={`Abstract Tiers (${HARNESS_LABELS[runHarness].name} Mapping)`}>
                              {(["reasoning", "coding", "fast", "default"] as const).map((tier) => (
                                <option key={tier} value={tier}>
                                  {tier} → {harnessModels?.tier_map?.[runHarness]?.[tier] || tier}
                                </option>
                              ))}
                            </optgroup>
                            <optgroup label={`Native ${HARNESS_LABELS[runHarness].name} Models`}>
                              {(harnessModels?.native_models?.[runHarness] || []).map((m) => (
                                <option key={m.id} value={m.id}>
                                  {m.label}
                                </option>
                              ))}
                            </optgroup>
                          </select>
                        </div>
                        <div>
                          <label className="block text-slate-400 mb-1">Max Turns</label>
                          <input
                            type="number"
                            value={selectedSubagent.max_turns}
                            onChange={(e) =>
                              handleCanvasBlueprintChange({
                                ...selectedBlueprint,
                                subagents: selectedBlueprint.subagents.map((s) =>
                                  s.id === selectedSubagent.id
                                    ? { ...s, max_turns: Number(e.target.value) || 12 }
                                    : s
                                ),
                              })
                            }
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5"
                          />
                        </div>
                      </div>

                      {/* Per-Harness Explicit Model Overrides for Subagent + Best-Practice Advice */}
                      <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-bold text-cyan-300">
                            Per-Harness Model Pinning (`{selectedSubagent.id}`)
                          </span>
                          <span className="text-[10px] text-slate-500">Configure model per harness</span>
                        </div>
                        <div className="grid grid-cols-3 gap-1.5">
                          {(["claude_code", "antigravity", "opencode"] as HarnessType[]).map((h) => (
                            <div key={h}>
                              <label className="block text-[10px] text-slate-400 mb-0.5">
                                {HARNESS_LABELS[h].name}
                              </label>
                              <select
                                value={selectedSubagent.harness_models?.[h] || ""}
                                onChange={(e) => {
                                  const nextMap = {
                                    ...(selectedSubagent.harness_models || {}),
                                  };
                                  if (e.target.value) nextMap[h] = e.target.value;
                                  else delete nextMap[h];
                                  handleCanvasBlueprintChange({
                                    ...selectedBlueprint,
                                    subagents: selectedBlueprint.subagents.map((s) =>
                                      s.id === selectedSubagent.id
                                        ? { ...s, harness_models: nextMap }
                                        : s
                                    ),
                                  });
                                }}
                                className={`w-full bg-slate-900 border rounded px-1.5 py-1 text-[10px] font-mono ${runHarness === h
                                  ? "border-cyan-500/70 text-cyan-200"
                                  : "border-slate-800 text-slate-300"
                                  }`}
                              >
                                <option value="">
                                  Tier Default (
                                  {harnessModels?.tier_map?.[h]?.[selectedSubagent.model] ||
                                    selectedSubagent.model}
                                  )
                                </option>
                                {(harnessModels?.native_models?.[h] || []).map((m) => (
                                  <option key={m.id} value={m.id}>
                                    {m.id}
                                  </option>
                                ))}
                              </select>
                            </div>
                          ))}
                        </div>
                        <div className="text-[10px] text-emerald-300/90 leading-relaxed pt-1 border-t border-slate-800/80">
                          💡{" "}
                          {!selectedSubagent.permissions.allow_write &&
                            !selectedSubagent.permissions.allow_shell
                            ? harnessModels?.best_practices?.reasoning
                            : !selectedSubagent.permissions.allow_write &&
                              selectedSubagent.permissions.allow_shell
                              ? harnessModels?.best_practices?.fast
                              : harnessModels?.best_practices?.coding}
                        </div>
                      </div>
                      <div className="flex items-center gap-4 pt-1">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={selectedSubagent.permissions.allow_write}
                            onChange={(e) =>
                              handleCanvasBlueprintChange({
                                ...selectedBlueprint,
                                subagents: selectedBlueprint.subagents.map((s) =>
                                  s.id === selectedSubagent.id
                                    ? {
                                      ...s,
                                      permissions: {
                                        ...s.permissions,
                                        allow_write: e.target.checked,
                                      },
                                    }
                                    : s
                                ),
                              })
                            }
                          />
                          <span>Allow Write/Edit</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={selectedSubagent.permissions.allow_shell}
                            onChange={(e) =>
                              handleCanvasBlueprintChange({
                                ...selectedBlueprint,
                                subagents: selectedBlueprint.subagents.map((s) =>
                                  s.id === selectedSubagent.id
                                    ? {
                                      ...s,
                                      permissions: {
                                        ...s.permissions,
                                        allow_shell: e.target.checked,
                                      },
                                    }
                                    : s
                                ),
                              })
                            }
                          />
                          <span>Allow Bash/Shell</span>
                        </label>
                      </div>
                      <div>
                        <label className="block text-slate-400 mb-1">Subagent System Prompt</label>
                        <textarea
                          rows={6}
                          value={selectedSubagent.system_prompt}
                          onChange={(e) =>
                            handleCanvasBlueprintChange({
                              ...selectedBlueprint,
                              subagents: selectedBlueprint.subagents.map((s) =>
                                s.id === selectedSubagent.id
                                  ? { ...s, system_prompt: e.target.value }
                                  : s
                              ),
                            })
                          }
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 font-mono text-[11px] leading-relaxed"
                        />
                      </div>

                      {/* Assigned MCP Servers (CRUD & Assign from Subagent) */}
                      <div className="p-2.5 rounded-xl bg-slate-950 border border-purple-800/50 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-purple-300">
                            Assigned MCP Servers ({(selectedSubagent.mcp_servers || []).length}/{(selectedBlueprint.mcp_servers || []).length})
                          </span>
                          <button
                            onClick={() => handleAddMcpServer(selectedSubagent.id)}
                            className="px-2 py-0.5 rounded bg-purple-700 hover:bg-purple-600 text-white text-[10px] font-semibold cursor-pointer"
                          >
                            + Add &amp; Assign MCP
                          </button>
                        </div>
                        {(selectedBlueprint.mcp_servers || []).length === 0 ? (
                          <div className="text-[10px] text-slate-400">
                            No MCP servers configured yet. Click <strong>+ Add &amp; Assign MCP</strong> to add one for this subagent.
                          </div>
                        ) : (
                          <div className="space-y-1">
                            {(selectedBlueprint.mcp_servers || []).map((srv) => {
                              const assigned = (selectedSubagent.mcp_servers || []).includes(srv.id);
                              return (
                                <div key={srv.id} className="flex items-center justify-between gap-2 px-2 py-1 rounded bg-slate-900 border border-slate-800">
                                  <label className="flex items-center gap-2 cursor-pointer min-w-0 flex-1">
                                    <input
                                      type="checkbox"
                                      checked={assigned}
                                      onChange={() => toggleAgentMcpServer("subagent", selectedSubagent.id, srv.id)}
                                    />
                                    <span className="font-mono text-[11px] text-purple-300 truncate">{srv.id}</span>
                                    <span className="text-[9px] text-slate-400 uppercase">{srv.transport}</span>
                                  </label>
                                  <div className="flex items-center gap-1 shrink-0">
                                    <button
                                      onClick={() => setSelectedNodeId(srv.id)}
                                      className="p-0.5 text-slate-400 hover:text-purple-300 cursor-pointer"
                                      title={`Edit MCP server '${srv.id}'`}
                                    >
                                      <Pencil className="w-3 h-3" />
                                    </button>
                                    <button
                                      onClick={() => deleteMcpServer(srv.id)}
                                      className="p-0.5 text-slate-500 hover:text-rose-400 cursor-pointer"
                                      title={`Delete MCP server '${srv.id}'`}
                                    >
                                      <Trash2 className="w-3 h-3" />
                                    </button>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {selectedSkill && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">
                          Skill: /{selectedSkill.id}
                        </span>
                        <button
                          onClick={() => {
                            const updated: AgentArchitecture = {
                              ...selectedBlueprint,
                              skills: selectedBlueprint.skills.filter((sk) => sk.id !== selectedSkill.id),
                            };
                            handleCanvasBlueprintChange(updated);
                            setSelectedNodeId(selectedBlueprint.orchestrator.id);
                          }}
                          className="text-rose-400 hover:text-rose-300 flex items-center gap-1 text-[11px]"
                        >
                          <Trash2 className="w-3.5 h-3.5" /> Remove
                        </button>
                      </div>
                      <div>
                        <label className="block text-slate-400 mb-1">
                          Skill ID / Folder Slug <span className="text-[10px] font-mono text-emerald-400">(skills/{selectedSkill.id}/SKILL.md)</span>
                        </label>
                        <input
                          key={`skill-id-${selectedSkill.id}`}
                          defaultValue={selectedSkill.id}
                          onBlur={(e) => {
                            if (e.target.value.trim() && e.target.value.trim() !== selectedSkill.id) {
                              renameSkillId(selectedSkill.id, e.target.value);
                            }
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              const val = (e.target as HTMLInputElement).value;
                              if (val.trim() && val.trim() !== selectedSkill.id) {
                                renameSkillId(selectedSkill.id, val);
                              }
                            }
                          }}
                          placeholder="e.g. react-expert"
                          className="w-full bg-slate-950 border border-emerald-700/60 rounded-lg px-2.5 py-1.5 font-mono text-emerald-300"
                        />
                      </div>
                      <div>
                        <label className="block text-slate-400 mb-1">Skill / Template Title</label>
                        <input
                          value={selectedSkill.name}
                          onChange={(e) =>
                            handleCanvasBlueprintChange({
                              ...selectedBlueprint,
                              skills: selectedBlueprint.skills.map((sk) =>
                                sk.id === selectedSkill.id ? { ...sk, name: e.target.value } : sk
                              ),
                            })
                          }
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5"
                        />
                      </div>
                      <div>
                        <label className="block text-slate-400 mb-1">When to Use (Description)</label>
                        <input
                          value={selectedSkill.description}
                          onChange={(e) =>
                            handleCanvasBlueprintChange({
                              ...selectedBlueprint,
                              skills: selectedBlueprint.skills.map((sk) =>
                                sk.id === selectedSkill.id ? { ...sk, description: e.target.value } : sk
                              ),
                            })
                          }
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5"
                        />
                      </div>
                      {/* Optional Folder-Backed Skill (SKILL.md + references/, scripts/, assets/, resources/) */}
                      <div className="p-2.5 rounded-xl bg-slate-950 border border-emerald-800/60 space-y-2">
                        <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-300">
                          Skill Folder Path (Optional — bundles references/, scripts/, assets/)
                        </div>
                        <div className="flex items-center gap-1.5">
                          <input
                            placeholder="e.g. D:/MySkills/react-expert or skills/react-expert"
                            value={selectedSkill.source_dir || ""}
                            onChange={(e) =>
                              handleCanvasBlueprintChange({
                                ...selectedBlueprint,
                                skills: selectedBlueprint.skills.map((sk) =>
                                  sk.id === selectedSkill.id ? { ...sk, source_dir: e.target.value || null } : sk
                                ),
                              })
                            }
                            className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 font-mono text-[11px] text-emerald-200"
                          />
                          <button
                            onClick={async () => {
                              const dir = (selectedSkill.source_dir || "").trim();
                              if (!dir) {
                                notify("Enter a local skill folder path first.", "err");
                                return;
                              }
                              try {
                                const info = await api.inspectSkillDir(dir);
                                renameSkillId(selectedSkill.id, info.id || selectedSkill.id, {
                                  name: info.name || selectedSkill.name,
                                  description: info.description || selectedSkill.description,
                                  source_dir: info.source_dir,
                                  instructions: info.instructions_preview || selectedSkill.instructions,
                                });
                                notify(
                                  `Loaded '/${info.id}' (${info.files.length} files: ${info.counts.references} refs, ${info.counts.scripts} scripts, ${info.counts.assets + info.counts.resources} assets/resources)`
                                );
                              } catch (err: unknown) {
                                notify(err instanceof Error ? err.message : "Failed to inspect skill folder", "err");
                              }
                            }}
                            className="px-2.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-[11px] cursor-pointer shrink-0"
                            title="Parse SKILL.md frontmatter and discover references/, scripts/, assets/, resources/"
                          >
                            Load Folder
                          </button>
                        </div>
                        <div className="text-[10px] text-slate-400">
                          When set, compiling &amp; deploying copies <code className="text-emerald-300">SKILL.md</code> plus all subfolders (<code className="text-cyan-300">references/</code>, <code className="text-cyan-300">scripts/</code>, <code className="text-cyan-300">assets/</code>, <code className="text-cyan-300">resources/</code>) into every harness.
                        </div>
                      </div>
                      <div>
                        <label className="block text-slate-400 mb-1">
                          Template Instructions / Markdown Deliverable Format
                        </label>
                        <textarea
                          rows={8}
                          value={selectedSkill.instructions}
                          onChange={(e) =>
                            handleCanvasBlueprintChange({
                              ...selectedBlueprint,
                              skills: selectedBlueprint.skills.map((sk) =>
                                sk.id === selectedSkill.id ? { ...sk, instructions: e.target.value } : sk
                              ),
                            })
                          }
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 font-mono text-[11px] leading-relaxed"
                        />
                      </div>
                    </div>
                  )}

                  {selectedHook && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-wider text-amber-400">
                          Lifecycle Guardrail Hook: {selectedHook.id}
                        </span>
                        <button
                          onClick={() => {
                            const nextLayoutNodes = { ...selectedBlueprint.visual_layout.nodes };
                            delete nextLayoutNodes[selectedHook.id];
                            const updated: AgentArchitecture = {
                              ...selectedBlueprint,
                              hooks: selectedBlueprint.hooks.filter((h) => h.id !== selectedHook.id),
                              topology: {
                                ...selectedBlueprint.topology,
                                edges: selectedBlueprint.topology.edges.filter(
                                  (e) => e.source !== selectedHook.id && e.target !== selectedHook.id
                                ),
                              },
                              visual_layout: { nodes: nextLayoutNodes },
                            };
                            handleCanvasBlueprintChange(updated);
                            setSelectedNodeId(selectedBlueprint.orchestrator.id);
                            notify(`Removed guardrail hook '${selectedHook.id}'`);
                          }}
                          className="text-rose-400 hover:text-rose-300 flex items-center gap-1 text-[11px] cursor-pointer"
                          title="Delete this guardrail hook node (works even when orphan or disconnected)"
                        >
                          <Trash2 className="w-3.5 h-3.5" /> Remove
                        </button>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-slate-400 mb-1">Target Agent</label>
                          <select
                            value={selectedHook.target_agent}
                            onChange={(e) =>
                              handleCanvasBlueprintChange({
                                ...selectedBlueprint,
                                hooks: selectedBlueprint.hooks.map((h) =>
                                  h.id === selectedHook.id ? { ...h, target_agent: e.target.value } : h
                                ),
                              })
                            }
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 font-mono text-[11px]"
                          >
                            <option value="*">* (All Agents)</option>
                            <option value={selectedBlueprint.orchestrator.id}>
                              {selectedBlueprint.orchestrator.id} (Orchestrator)
                            </option>
                            {selectedBlueprint.subagents.map((sa) => (
                              <option key={sa.id} value={sa.id}>
                                {sa.id} ({sa.name})
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-slate-400 mb-1">Action</label>
                          <select
                            value={selectedHook.action}
                            onChange={(e) =>
                              handleCanvasBlueprintChange({
                                ...selectedBlueprint,
                                hooks: selectedBlueprint.hooks.map((h) =>
                                  h.id === selectedHook.id
                                    ? { ...h, action: e.target.value as typeof selectedHook.action }
                                    : h
                                ),
                              })
                            }
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
                          >
                            <option value="block">block</option>
                            <option value="warn">warn</option>
                            <option value="allow">allow</option>
                            <option value="run_command">run_command</option>
                          </select>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-slate-400 mb-1">Lifecycle Event</label>
                          <select
                            value={selectedHook.event}
                            onChange={(e) =>
                              handleCanvasBlueprintChange({
                                ...selectedBlueprint,
                                hooks: selectedBlueprint.hooks.map((h) =>
                                  h.id === selectedHook.id
                                    ? { ...h, event: e.target.value as typeof selectedHook.event }
                                    : h
                                ),
                              })
                            }
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
                          >
                            <option value="PreToolUse">PreToolUse</option>
                            <option value="PostToolUse">PostToolUse</option>
                            <option value="SubagentStop">SubagentStop</option>
                            <option value="Stop">Stop</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-slate-400 mb-1">Tool Regex Matcher</label>
                          <input
                            value={selectedHook.matcher}
                            onChange={(e) =>
                              handleCanvasBlueprintChange({
                                ...selectedBlueprint,
                                hooks: selectedBlueprint.hooks.map((h) =>
                                  h.id === selectedHook.id ? { ...h, matcher: e.target.value } : h
                                ),
                              })
                            }
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 font-mono"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="block text-slate-400 mb-1">Block / Feedback Message</label>
                        <textarea
                          rows={3}
                          value={selectedHook.message}
                          onChange={(e) =>
                            handleCanvasBlueprintChange({
                              ...selectedBlueprint,
                              hooks: selectedBlueprint.hooks.map((h) =>
                                h.id === selectedHook.id ? { ...h, message: e.target.value } : h
                              ),
                            })
                          }
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2"
                        />
                      </div>
                    </div>
                  )}

                  {selectedMcpServer && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-wider text-purple-400">
                          MCP Server: {selectedMcpServer.id}
                        </span>
                        <button
                          onClick={() => deleteMcpServer(selectedMcpServer.id)}
                          className="text-rose-400 hover:text-rose-300 flex items-center gap-1 text-[11px] cursor-pointer"
                          title="Delete this MCP server and unassign from all agents"
                        >
                          <Trash2 className="w-3.5 h-3.5" /> Remove
                        </button>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-slate-400 mb-1">
                            MCP Server ID <span className="text-[10px] text-slate-500">(Enter/blur)</span>
                          </label>
                          <input
                            key={`mcp-id-${selectedMcpServer.id}`}
                            defaultValue={selectedMcpServer.id}
                            onBlur={(e) => {
                              if (e.target.value.trim() && e.target.value.trim() !== selectedMcpServer.id) {
                                renameMcpServerId(selectedMcpServer.id, e.target.value);
                              }
                            }}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                const val = (e.target as HTMLInputElement).value;
                                if (val.trim() && val.trim() !== selectedMcpServer.id) {
                                  renameMcpServerId(selectedMcpServer.id, val);
                                }
                              }
                            }}
                            className="w-full bg-slate-950 border border-purple-700/60 rounded-lg px-2.5 py-1.5 font-mono text-purple-300"
                          />
                        </div>
                        <div>
                          <label className="block text-slate-400 mb-1">Transport</label>
                          <select
                            value={selectedMcpServer.transport}
                            onChange={(e) =>
                              handleCanvasBlueprintChange({
                                ...selectedBlueprint,
                                mcp_servers: (selectedBlueprint.mcp_servers || []).map((m) =>
                                  m.id === selectedMcpServer.id
                                    ? { ...m, transport: e.target.value as "stdio" | "sse" | "http" }
                                    : m
                                ),
                              })
                            }
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 font-mono"
                          >
                            <option value="stdio">stdio (local process)</option>
                            <option value="http">http (remote streamable HTTP)</option>
                            <option value="sse">sse (remote SSE endpoint)</option>
                          </select>
                        </div>
                      </div>

                      <div>
                        <label className="block text-slate-400 mb-1">Description (Tools &amp; Purpose)</label>
                        <input
                          value={selectedMcpServer.description || ""}
                          onChange={(e) =>
                            handleCanvasBlueprintChange({
                              ...selectedBlueprint,
                              mcp_servers: (selectedBlueprint.mcp_servers || []).map((m) =>
                                m.id === selectedMcpServer.id ? { ...m, description: e.target.value } : m
                              ),
                            })
                          }
                          placeholder="e.g. Queries PostgreSQL schemas and read-only analytics"
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5"
                        />
                      </div>

                      {selectedMcpServer.transport === "stdio" ? (
                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <label className="block text-slate-400 mb-1">Command</label>
                            <input
                              value={selectedMcpServer.command || ""}
                              onChange={(e) =>
                                handleCanvasBlueprintChange({
                                  ...selectedBlueprint,
                                  mcp_servers: (selectedBlueprint.mcp_servers || []).map((m) =>
                                    m.id === selectedMcpServer.id ? { ...m, command: e.target.value } : m
                                  ),
                                })
                              }
                              placeholder="npx"
                              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 font-mono"
                            />
                          </div>
                          <div className="col-span-2">
                            <label className="block text-slate-400 mb-1">Args (space-separated)</label>
                            <input
                              value={(selectedMcpServer.args || []).join(" ")}
                              onChange={(e) =>
                                handleCanvasBlueprintChange({
                                  ...selectedBlueprint,
                                  mcp_servers: (selectedBlueprint.mcp_servers || []).map((m) =>
                                    m.id === selectedMcpServer.id
                                      ? {
                                          ...m,
                                          args: e.target.value.split(/\s+/).filter(Boolean),
                                        }
                                      : m
                                  ),
                                })
                              }
                              placeholder="-y @modelcontextprotocol/server-github"
                              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 font-mono"
                            />
                          </div>
                        </div>
                      ) : (
                        <div>
                          <label className="block text-slate-400 mb-1">Remote MCP Endpoint URL</label>
                          <input
                            value={selectedMcpServer.url || ""}
                            onChange={(e) =>
                              handleCanvasBlueprintChange({
                                ...selectedBlueprint,
                                mcp_servers: (selectedBlueprint.mcp_servers || []).map((m) =>
                                  m.id === selectedMcpServer.id ? { ...m, url: e.target.value } : m
                                ),
                              })
                            }
                            placeholder="https://mcp.internal.company.com/sse"
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 font-mono text-purple-200"
                          />
                        </div>
                      )}

                      <div>
                        <label className="block text-slate-400 mb-1">
                          Environment Variables (one per line: <code>KEY=VALUE</code>)
                        </label>
                        <textarea
                          rows={3}
                          key={`mcp-env-${selectedMcpServer.id}`}
                          defaultValue={Object.entries(selectedMcpServer.env || {})
                            .map(([k, v]) => `${k}=${v}`)
                            .join("\n")}
                          onBlur={(e) => {
                            const nextEnv: Record<string, string> = {};
                            e.target.value.split("\n").forEach((line) => {
                              const idx = line.indexOf("=");
                              if (idx > 0) {
                                const k = line.slice(0, idx).trim();
                                const v = line.slice(idx + 1).trim();
                                if (k) nextEnv[k] = v;
                              }
                            });
                            handleCanvasBlueprintChange({
                              ...selectedBlueprint,
                              mcp_servers: (selectedBlueprint.mcp_servers || []).map((m) =>
                                m.id === selectedMcpServer.id ? { ...m, env: nextEnv } : m
                              ),
                            });
                          }}
                          placeholder={"GITHUB_PERSONAL_ACCESS_TOKEN=${GITHUB_TOKEN}\nPOSTGRES_URL=${DATABASE_URL}"}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 font-mono text-[11px]"
                        />
                      </div>

                      <div className="p-2.5 rounded-xl bg-slate-950 border border-purple-800/50 space-y-1.5">
                        <div className="text-[10px] font-bold uppercase tracking-wider text-purple-300">
                          Assigned Agents &amp; Subagents
                        </div>
                        <label className="flex items-center gap-2 cursor-pointer text-[11px]">
                          <input
                            type="checkbox"
                            checked={(selectedBlueprint.orchestrator.mcp_servers || []).includes(selectedMcpServer.id)}
                            onChange={() =>
                              toggleAgentMcpServer("orchestrator", selectedBlueprint.orchestrator.id, selectedMcpServer.id)
                            }
                          />
                          <span className="font-mono text-indigo-300">{selectedBlueprint.orchestrator.id}</span>
                          <span className="text-slate-400">({selectedBlueprint.orchestrator.name})</span>
                        </label>
                        {selectedBlueprint.subagents.map((sa) => (
                          <label key={sa.id} className="flex items-center gap-2 cursor-pointer text-[11px]">
                            <input
                              type="checkbox"
                              checked={(sa.mcp_servers || []).includes(selectedMcpServer.id)}
                              onChange={() => toggleAgentMcpServer("subagent", sa.id, selectedMcpServer.id)}
                            />
                            <span className="font-mono text-cyan-300">{sa.id}</span>
                            <span className="text-slate-400">({sa.name})</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Topology Edges Table — Separated into Workflow Handoffs (Agent -> Agent) and Skill Assignments (Agent -> Skill) */}
                  {(() => {
                    const agentIds = new Set([
                      selectedBlueprint.orchestrator.id,
                      ...selectedBlueprint.subagents.map((s) => s.id),
                    ]);
                    const skillIds = new Set(selectedBlueprint.skills.map((s) => s.id));
                    const workflowEdges = selectedBlueprint.topology.edges
                      .filter((e) => agentIds.has(e.source) && agentIds.has(e.target))
                      .sort((a, b) => a.order - b.order);
                    const skillEdges = selectedBlueprint.topology.edges
                      .filter(
                        (e) =>
                          (agentIds.has(e.source) && skillIds.has(e.target)) ||
                          (skillIds.has(e.source) && agentIds.has(e.target))
                      )
                      .map((e) =>
                        skillIds.has(e.source)
                          ? { ...e, source: e.target, target: e.source, required: false, max_loops: 1 }
                          : e
                      );

                    const commitEdges = (
                      nextWorkflow: typeof workflowEdges,
                      nextSkills: typeof skillEdges
                    ) => {
                      const renumberedWorkflow = nextWorkflow.map((ed, idx) => ({
                        ...ed,
                        order: idx + 1,
                      }));
                      const renumberedSkills = nextSkills.map((ed, idx) => ({
                        ...ed,
                        order: renumberedWorkflow.length + idx + 1,
                        required: false,
                        max_loops: 1,
                      }));
                      handleCanvasBlueprintChange({
                        ...selectedBlueprint,
                        topology: {
                          ...selectedBlueprint.topology,
                          edges: [...renumberedWorkflow, ...renumberedSkills],
                        },
                      });
                    };

                    const moveWorkflowEdge = (index: number, delta: -1 | 1) => {
                      const targetIdx = index + delta;
                      if (targetIdx < 0 || targetIdx >= workflowEdges.length) return;
                      const reordered = [...workflowEdges];
                      const [moved] = reordered.splice(index, 1);
                      reordered.splice(targetIdx, 0, moved);
                      commitEdges(reordered, skillEdges);
                    };

                    return (
                      <div className="pt-3 border-t border-slate-800 space-y-4">
                        {/* 1. Agent-to-Agent Workflow Handoff Edges */}
                        <div>
                          <div className="text-xs font-bold uppercase tracking-wider text-cyan-300 mb-2">
                            Workflow Handoff Edges ({workflowEdges.length})
                          </div>
                          {workflowEdges.length === 0 ? (
                            <div className="text-[11px] text-slate-500 italic">
                              No agent-to-agent handoffs yet. Drag from an Orchestrator or Subagent handle to another Subagent on the canvas.
                            </div>
                          ) : (
                            <div className="space-y-2">
                              {workflowEdges.map((edge, idx) => (
                                <div
                                  key={edge.id}
                                  className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5"
                                >
                                  <div className="flex items-center justify-between gap-1.5">
                                    <div className="flex items-center gap-1.5 font-mono text-[11px] text-cyan-300 min-w-0 flex-wrap">
                                      <span className="px-1.5 py-0.2 rounded bg-cyan-950/80 border border-cyan-800/60 text-cyan-200 font-bold">
                                        #{idx + 1}
                                      </span>
                                      <span className="truncate">{edge.source}</span>
                                      <ArrowRight className="w-3 h-3 shrink-0" />
                                      <span className="truncate">{edge.target}</span>
                                    </div>
                                    <div className="flex items-center gap-1 shrink-0">
                                      <button
                                        onClick={() => moveWorkflowEdge(idx, -1)}
                                        disabled={idx === 0}
                                        className="px-1 py-0.5 rounded bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white disabled:opacity-25 text-[10px] cursor-pointer"
                                        title="Move step earlier"
                                      >
                                        ↑
                                      </button>
                                      <button
                                        onClick={() => moveWorkflowEdge(idx, 1)}
                                        disabled={idx === workflowEdges.length - 1}
                                        className="px-1 py-0.5 rounded bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white disabled:opacity-25 text-[10px] cursor-pointer"
                                        title="Move step later"
                                      >
                                        ↓
                                      </button>
                                      <button
                                        onClick={() =>
                                          commitEdges(
                                            workflowEdges.filter((ed) => ed.id !== edge.id),
                                            skillEdges
                                          )
                                        }
                                        className="p-0.5 text-slate-500 hover:text-rose-400 cursor-pointer"
                                        title="Delete handoff edge"
                                      >
                                        <Trash2 className="w-3.5 h-3.5" />
                                      </button>
                                    </div>
                                  </div>

                                  <div className="flex items-center gap-1.5">
                                    <button
                                      onClick={() =>
                                        commitEdges(
                                          workflowEdges.map((ed) =>
                                            ed.id === edge.id ? { ...ed, required: !ed.required } : ed
                                          ),
                                          skillEdges
                                        )
                                      }
                                      className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase cursor-pointer border ${
                                        edge.required
                                          ? "bg-sky-950/80 text-sky-300 border-sky-700/60"
                                          : "bg-amber-950/70 text-amber-300 border-amber-700/60"
                                      }`}
                                      title="Toggle Required vs Conditional handoff"
                                    >
                                      {edge.required ? "Required" : "Conditional"}
                                    </button>
                                    <select
                                      value={edge.max_loops}
                                      onChange={(e) =>
                                        commitEdges(
                                          workflowEdges.map((ed) =>
                                            ed.id === edge.id
                                              ? { ...ed, max_loops: Number(e.target.value) }
                                              : ed
                                          ),
                                          skillEdges
                                        )
                                      }
                                      className="bg-slate-900 border border-slate-800 rounded px-1.5 py-0.5 text-[10px] text-slate-300"
                                      title="Max retry loops along this edge"
                                    >
                                      {[1, 2, 3, 5, 10].map((n) => (
                                        <option key={n} value={n}>
                                          ≤{n}x
                                        </option>
                                      ))}
                                    </select>
                                    <input
                                      value={edge.condition}
                                      onChange={(e) =>
                                        commitEdges(
                                          workflowEdges.map((ed) =>
                                            ed.id === edge.id
                                              ? { ...ed, condition: e.target.value }
                                              : ed
                                          ),
                                          skillEdges
                                        )
                                      }
                                      className="flex-1 min-w-0 bg-slate-900/60 border border-slate-800/80 rounded px-2 py-0.5 text-[11px] text-slate-300 focus:text-white focus:border-cyan-600 outline-none"
                                      placeholder="Trigger / handoff condition..."
                                    />
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* 2. Skill Assignments (Agent -> Skill) */}
                        <div className="pt-2 border-t border-slate-800/70">
                          <div className="text-xs font-bold uppercase tracking-wider text-emerald-400 mb-2">
                            Skill Assignments ({skillEdges.length})
                          </div>
                          {skillEdges.length === 0 ? (
                            <div className="text-[11px] text-slate-500 italic">
                              No agent-specific skill bindings. Drag between any Agent and Skill node on the canvas to assign a skill.
                            </div>
                          ) : (
                            <div className="space-y-1.5">
                              {skillEdges.map((edge) => (
                                <div
                                  key={edge.id}
                                  className="p-2 rounded-lg bg-slate-950 border border-emerald-900/50 flex items-center justify-between gap-2"
                                >
                                  <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-1.5 font-mono text-[11px] text-emerald-300">
                                      <span className="text-cyan-300">{edge.source}</span>
                                      <ArrowRight className="w-3 h-3 text-emerald-500 shrink-0" />
                                      <span className="truncate">/{edge.target}</span>
                                    </div>
                                    <input
                                      value={edge.condition}
                                      onChange={(e) =>
                                        commitEdges(
                                          workflowEdges,
                                          skillEdges.map((ed) =>
                                            ed.id === edge.id
                                              ? { ...ed, condition: e.target.value }
                                              : ed
                                          )
                                        )
                                      }
                                      className="mt-0.5 w-full bg-transparent text-[10px] text-slate-400 focus:text-white outline-none"
                                    />
                                  </div>
                                  <button
                                    onClick={() =>
                                      commitEdges(
                                        workflowEdges,
                                        skillEdges.filter((ed) => ed.id !== edge.id)
                                      )
                                    }
                                    className="text-slate-500 hover:text-rose-400 cursor-pointer"
                                    title="Unbind skill from agent"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })()}
                </div>
              )}

              {/* Panel 1.25: Custom & Executable Slash Commands Manager */}
              {studioRightPanel === "commands" && (
                <div className="flex-1 flex flex-col p-4 overflow-y-auto space-y-4 text-xs">
                  <div>
                    <div className="font-bold text-white text-sm">
                      Executable Custom Commands ({(selectedBlueprint.commands || []).length + selectedBlueprint.skills.length + 3})
                    </div>
                    <div className="text-[11px] text-slate-400">
                      Configure reusable slash commands that compile into{" "}
                      <code className="text-cyan-300">.opencode/command/</code>,{" "}
                      <code className="text-cyan-300">.claude/commands/</code>, and{" "}
                      <code className="text-cyan-300">.agents/skills/</code>.
                    </div>
                  </div>

                  {/* Add / Edit Custom Command Form */}
                  <div className="p-3 rounded-xl bg-slate-950 border border-indigo-800/60 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <div className="text-[11px] font-bold uppercase tracking-wider text-indigo-300">
                        {editingCmdId ? `Edit Custom Command: /${editingCmdId}` : "+ Add Custom Command"}
                      </div>
                      {editingCmdId && (
                        <button
                          onClick={() => {
                            setEditingCmdId(null);
                            setNewCmdId("");
                            setNewCmdDesc("");
                            setNewCmdPrompt("");
                            setNewCmdAgent("");
                          }}
                          className="text-[10px] text-slate-400 hover:text-white cursor-pointer"
                        >
                          Cancel Edit
                        </button>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[10px] text-slate-400 mb-0.5">Command Slug</label>
                        <input
                          placeholder="e.g. build-ui-epic"
                          value={newCmdId}
                          onChange={(e) => setNewCmdId(e.target.value)}
                          className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 font-mono text-[11px] text-emerald-300"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-400 mb-0.5">Target Agent (Optional)</label>
                        <select
                          value={newCmdAgent}
                          onChange={(e) => setNewCmdAgent(e.target.value)}
                          className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 text-[11px] text-slate-200"
                        >
                          <option value="">Default (Orchestrator)</option>
                          <option value={selectedBlueprint.orchestrator.id}>
                            {selectedBlueprint.orchestrator.name} ({selectedBlueprint.orchestrator.id})
                          </option>
                          {selectedBlueprint.subagents.map((sa) => (
                            <option key={sa.id} value={sa.id}>
                              {sa.name} ({sa.id})
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div>
                      <label className="block text-[10px] text-slate-400 mb-0.5">Short Description</label>
                      <input
                        placeholder="e.g. Implement the next UI Epic from external specs using planner -> coder -> verifier"
                        value={newCmdDesc}
                        onChange={(e) => setNewCmdDesc(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 text-[11px]"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] text-slate-400 mb-0.5">
                        Command Prompt / Execution Instructions
                      </label>
                      <textarea
                        rows={4}
                        placeholder="Write the exact instructions the agent should execute when the user invokes this command..."
                        value={newCmdPrompt}
                        onChange={(e) => setNewCmdPrompt(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2 font-mono text-[11px] leading-relaxed"
                      />
                    </div>
                    <button
                      onClick={() => {
                        const slug = sanitizeSlug(newCmdId.replace(/^\/+/, ""));
                        if (!slug || !newCmdPrompt.trim()) {
                          notify("Please enter both a Command Slug and Prompt instructions.", "err");
                          return;
                        }
                        const existing = selectedBlueprint.commands || [];
                        const nextCmd = {
                          id: slug,
                          description: newCmdDesc.trim() || `Run custom command /${slug}`,
                          prompt: newCmdPrompt.trim(),
                          agent: newCmdAgent.trim() || null,
                        };
                        const filtered = existing.filter(
                          (c) => c.id !== slug && c.id !== editingCmdId
                        );
                        handleCanvasBlueprintChange({
                          ...selectedBlueprint,
                          commands: [...filtered, nextCmd],
                        });
                        setEditingCmdId(null);
                        setNewCmdId("");
                        setNewCmdDesc("");
                        setNewCmdPrompt("");
                        setNewCmdAgent("");
                        notify(`Saved custom command '/${slug}' (auto-saving to blueprint)!`);
                      }}
                      className="w-full py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs cursor-pointer"
                    >
                      {editingCmdId ? "Update Custom Command" : "+ Add Custom Command"}
                    </button>
                  </div>

                  {/* List of Custom Commands */}
                  <div className="space-y-2">
                    <div className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                      Your Custom Commands ({(selectedBlueprint.commands || []).length})
                    </div>
                    {(selectedBlueprint.commands || []).length === 0 ? (
                      <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-slate-400 text-[11px]">
                        No custom commands yet. Add one above (e.g. <code className="text-emerald-300">/build-ui-epic</code> or <code className="text-emerald-300">/review-pr</code>) and it will automatically compile for {HARNESS_LABELS[previewHarness].name}.
                      </div>
                    ) : (
                      (selectedBlueprint.commands || []).map((cmd) => {
                        const invokeText =
                          previewHarness === "antigravity"
                            ? `Run the ${cmd.id} skill`
                            : `/${cmd.id}`;
                        return (
                          <div
                            key={cmd.id}
                            className="p-2.5 rounded-xl bg-slate-950 border border-emerald-800/50 space-y-1.5"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-1.5 min-w-0">
                                <span className="font-mono font-bold text-emerald-300">/{cmd.id}</span>
                                <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-950 text-emerald-300 border border-emerald-800/60">
                                  Custom
                                </span>
                                {cmd.agent && (
                                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-cyan-300">
                                    @{cmd.agent}
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-1 shrink-0">
                                <button
                                  onClick={() => {
                                    navigator.clipboard.writeText(invokeText);
                                    notify(`Copied '${invokeText}' to clipboard!`);
                                  }}
                                  className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-[10px] cursor-pointer"
                                  title="Copy command invocation"
                                >
                                  Copy
                                </button>
                                <button
                                  onClick={() => {
                                    setEditingCmdId(cmd.id);
                                    setNewCmdId(cmd.id);
                                    setNewCmdDesc(cmd.description);
                                    setNewCmdPrompt(cmd.prompt);
                                    setNewCmdAgent(cmd.agent || "");
                                  }}
                                  className="p-1 text-slate-400 hover:text-indigo-300 cursor-pointer"
                                  title="Edit command"
                                >
                                  <Pencil className="w-3 h-3" />
                                </button>
                                <button
                                  onClick={() => {
                                    handleCanvasBlueprintChange({
                                      ...selectedBlueprint,
                                      commands: (selectedBlueprint.commands || []).filter(
                                        (c) => c.id !== cmd.id
                                      ),
                                    });
                                    notify(`Removed custom command '/${cmd.id}'`);
                                  }}
                                  className="p-1 text-slate-400 hover:text-rose-400 cursor-pointer"
                                  title="Delete command"
                                >
                                  <Trash2 className="w-3 h-3" />
                                </button>
                              </div>
                            </div>
                            <div className="text-[11px] text-slate-300">{cmd.description}</div>
                            <div className="text-[10px] text-slate-500 font-mono">
                              Run in {HARNESS_LABELS[previewHarness].name}: <span className="text-cyan-300">{invokeText}</span>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>

                  {/* Skill & Built-in Executable Commands Reference */}
                  <div className="space-y-2 pt-2 border-t border-slate-800">
                    <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                      Skill &amp; Built-In Executable Commands
                    </div>
                    {[
                      ...selectedBlueprint.skills.map((sk) => ({
                        id: sk.id,
                        desc: sk.description,
                        badge: "Skill",
                      })),
                      {
                        id: "verify-setup",
                        desc: "Verify installed agents, skills, and external documentation readability",
                        badge: "Built-in",
                      },
                      {
                        id: "generate-tba-pack",
                        desc: "Run the full TBA workflow to produce Workflows and Epics/User Stories",
                        badge: "Built-in",
                      },
                      {
                        id: "evaluate-project",
                        desc: "Verify deliverables on disk and prepare for HarnessForge evaluation",
                        badge: "Built-in",
                      },
                    ].map((item) => {
                      const invokeText =
                        previewHarness === "antigravity"
                          ? `Run the ${item.id} skill`
                          : `/${item.id}`;
                      return (
                        <div
                          key={`${item.badge}-${item.id}`}
                          className="p-2 rounded-lg bg-slate-950/70 border border-slate-800 flex items-center justify-between gap-2"
                        >
                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5">
                              <span className="font-mono text-cyan-300 font-semibold">/{item.id}</span>
                              <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 uppercase">
                                {item.badge}
                              </span>
                            </div>
                            <div className="text-[10px] text-slate-400 truncate">{item.desc}</div>
                          </div>
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(invokeText);
                              notify(`Copied '${invokeText}' to clipboard!`);
                            }}
                            className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-[10px] cursor-pointer shrink-0"
                          >
                            Copy
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Panel 1.5: Global Harness Models & Tier Configurator */}
              {studioRightPanel === "models" && harnessModels && (
                <div className="flex-1 flex flex-col p-4 overflow-y-auto space-y-4 text-xs">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-bold text-white text-sm">
                        Configure Models per Harness
                      </div>
                      <div className="text-[11px] text-slate-400">
                        Customize tier mappings & available models for Claude Code, Antigravity & OpenCode
                      </div>
                    </div>
                    <button
                      onClick={async () => {
                        try {
                          const synced = await api.syncHarnessModelsFromCli();
                          setHarnessModels(synced);
                          notify("Auto-discovered live models from installed agy & opencode CLIs!");
                        } catch (err: unknown) {
                          notify(err instanceof Error ? err.message : "Sync failed", "err");
                        }
                      }}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-cyan-950 hover:bg-cyan-900 border border-cyan-700/60 text-cyan-200 text-[11px] font-semibold cursor-pointer"
                    >
                      <RefreshCw className="w-3 h-3" /> Sync CLI Models
                    </button>
                  </div>

                  {/* Select which harness to configure */}
                  <div className="flex items-center gap-1.5">
                    {(["claude_code", "antigravity", "opencode"] as HarnessType[]).map((h) => (
                      <button
                        key={h}
                        onClick={() => {
                          setRunHarness(h);
                          setPreviewHarness(h);
                        }}
                        className={`flex-1 py-1.5 px-2 rounded-lg font-medium border text-[11px] cursor-pointer ${runHarness === h
                          ? "bg-indigo-600/25 border-indigo-500 text-white"
                          : "bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200"
                          }`}
                      >
                        {HARNESS_LABELS[h].name}
                      </button>
                    ))}
                  </div>

                  {/* Tier Mapping Editor for Active Harness */}
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2.5">
                    <div className="text-[11px] font-bold uppercase tracking-wider text-indigo-400">
                      {HARNESS_LABELS[runHarness].name} — Default Role Tier Mapping
                    </div>
                    {(["default", "reasoning", "coding", "fast"] as const).map((tier) => (
                      <div key={tier} className="grid grid-cols-3 items-center gap-2">
                        <span className="font-mono text-cyan-300 font-semibold">{tier}</span>
                        <select
                          value={harnessModels.tier_map[runHarness]?.[tier] || ""}
                          onChange={async (e) => {
                            const updatedTierMap = {
                              ...harnessModels.tier_map,
                              [runHarness]: {
                                ...harnessModels.tier_map[runHarness],
                                [tier]: e.target.value,
                              },
                            };
                            const saved = await api.updateHarnessModels({
                              tier_map: updatedTierMap,
                            });
                            setHarnessModels(saved);
                            if (selectedBlueprint) {
                              const comp = await api.compilePreview(
                                selectedBlueprint.metadata.id,
                                runHarness
                              );
                              setCompiledResult(comp);
                            }
                            notify(`Updated ${HARNESS_LABELS[runHarness].name} '${tier}' tier to ${e.target.value}`);
                          }}
                          className="col-span-2 bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 font-mono text-[11px] text-white"
                        >
                          {(harnessModels.native_models[runHarness] || []).map((m) => (
                            <option key={m.id} value={m.id}>
                              {m.label} ({m.id})
                            </option>
                          ))}
                        </select>
                      </div>
                    ))}
                  </div>

                  {/* Add Custom Native Model to Active Harness */}
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                    <div className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                      Add Custom Model to {HARNESS_LABELS[runHarness].name}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        placeholder="Model ID (e.g. provider/model-id)"
                        value={newCustomModelId}
                        onChange={(e) => setNewCustomModelId(e.target.value)}
                        className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 font-mono text-[11px]"
                      />
                      <input
                        placeholder="Display Label"
                        value={newCustomModelLabel}
                        onChange={(e) => setNewCustomModelLabel(e.target.value)}
                        className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-[11px]"
                      />
                    </div>
                    <button
                      onClick={async () => {
                        if (!newCustomModelId.trim()) return;
                        const currList = harnessModels.native_models[runHarness] || [];
                        const updatedNative = {
                          ...harnessModels.native_models,
                          [runHarness]: [
                            ...currList,
                            {
                              id: newCustomModelId.trim(),
                              label: newCustomModelLabel.trim() || newCustomModelId.trim(),
                              tier: "coding",
                            },
                          ],
                        };
                        const saved = await api.updateHarnessModels({
                          native_models: updatedNative,
                        });
                        setHarnessModels(saved);
                        setNewCustomModelId("");
                        setNewCustomModelLabel("");
                        notify(`Added model '${newCustomModelId.trim()}' to ${HARNESS_LABELS[runHarness].name}`);
                      }}
                      className="w-full py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs cursor-pointer"
                    >
                      + Register Model in {HARNESS_LABELS[runHarness].name}
                    </button>
                  </div>

                  {/* Enterprise OpenAI-Compatible LLM Hosting Platform (OpenCode) */}
                  {runHarness === "opencode" && (
                    <div className="p-3 rounded-xl bg-slate-950 border border-cyan-800/60 space-y-2.5">
                      <div>
                        <div className="text-[11px] font-bold uppercase tracking-wider text-cyan-300">
                          Enterprise OpenAI-Compatible LLM Provider (OpenCode)
                        </div>
                        <div className="text-[10px] text-slate-400 mt-0.5">
                          Compiles into <code className="text-cyan-300">opencode.json</code> (<code>@ai-sdk/openai-compatible</code>) &amp; registers models as <code className="text-emerald-300">&lt;provider_id&gt;/&lt;model_id&gt;</code>.
                        </div>
                      </div>

                      {/* Existing Configured Enterprise Providers */}
                      {(harnessModels.custom_providers || []).length > 0 && (
                        <div className="space-y-1.5">
                          {(harnessModels.custom_providers || []).map((prov) => (
                            <div
                              key={prov.id}
                              className="p-2 rounded-lg bg-slate-900 border border-slate-800 flex items-start justify-between gap-2"
                            >
                              <div className="min-w-0 space-y-0.5">
                                <div className="font-semibold text-white text-[11px] flex items-center gap-1.5">
                                  <span>{prov.name}</span>
                                  <span className="font-mono text-[10px] px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-300 border border-cyan-800/60">
                                    {prov.id}
                                  </span>
                                </div>
                                <div className="font-mono text-[10px] text-slate-400 truncate">
                                  {prov.base_url}
                                </div>
                                <div className="text-[10px] text-slate-400">
                                  API Key Env: <code className="text-amber-300">{`{env:${prov.api_key_env || "OPENAI_API_KEY"}}`}</code>
                                  {" · "}Models:{" "}
                                  <span className="font-mono text-emerald-300">
                                    {prov.models.map((m) => m.id).join(", ")}
                                  </span>
                                </div>
                              </div>
                              <button
                                onClick={async () => {
                                  const remaining = (harnessModels.custom_providers || []).filter(
                                    (p) => p.id !== prov.id
                                  );
                                  const cleanedOcModels = (harnessModels.native_models.opencode || []).filter(
                                    (m) => !m.id.startsWith(`${prov.id}/`)
                                  );
                                  const saved = await api.updateHarnessModels({
                                    custom_providers: remaining,
                                    native_models: {
                                      ...harnessModels.native_models,
                                      opencode: cleanedOcModels,
                                    },
                                  });
                                  setHarnessModels(saved);
                                  if (selectedBlueprint) {
                                    const comp = await api.compilePreview(selectedBlueprint.metadata.id, "opencode");
                                    setCompiledResult(comp);
                                  }
                                  notify(`Removed enterprise provider '${prov.id}'`);
                                }}
                                className="text-slate-500 hover:text-rose-400 p-1 cursor-pointer"
                                title="Remove enterprise provider"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Add / Update Enterprise Provider Form */}
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-[10px] text-slate-400 mb-0.5">Provider ID</label>
                          <input
                            placeholder="e.g. enterprise-llm"
                            value={entProvId}
                            onChange={(e) => setEntProvId(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 font-mono text-[11px]"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] text-slate-400 mb-0.5">Display Name</label>
                          <input
                            placeholder="e.g. Company LLM Gateway"
                            value={entProvName}
                            onChange={(e) => setEntProvName(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 text-[11px]"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="block text-[10px] text-slate-400 mb-0.5">
                          OpenAI-Compatible Base URL (ending in /v1)
                        </label>
                        <input
                          placeholder="https://llm.internal.company.com/v1"
                          value={entProvBaseUrl}
                          onChange={(e) => setEntProvBaseUrl(e.target.value)}
                          className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 font-mono text-[11px] text-cyan-200"
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-[10px] text-slate-400 mb-0.5">
                            API Key Env Variable Name
                          </label>
                          <input
                            placeholder="ENTERPRISE_LLM_API_KEY"
                            value={entProvApiKeyEnv}
                            onChange={(e) => setEntProvApiKeyEnv(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 font-mono text-[11px] text-amber-300"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] text-slate-400 mb-0.5">
                            Model IDs (comma-separated)
                          </label>
                          <input
                            placeholder="gpt-4o, llama-3.3-70b"
                            value={entProvModelsText}
                            onChange={(e) => setEntProvModelsText(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 font-mono text-[11px] text-emerald-300"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="block text-[10px] text-slate-400 mb-0.5">
                          Optional Custom Headers (one per line: <code>Header-Name: value</code>)
                        </label>
                        <textarea
                          rows={2}
                          placeholder={"X-Tenant-Id: engineering\nX-Api-Version: 2025-01"}
                          value={entProvHeaders}
                          onChange={(e) => setEntProvHeaders(e.target.value)}
                          className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 font-mono text-[11px] resize-none"
                        />
                      </div>

                      <button
                        onClick={async () => {
                          const pid = entProvId.trim().replace(/\s+/g, "-").toLowerCase();
                          const baseUrl = entProvBaseUrl.trim();
                          const modelIds = entProvModelsText
                            .split(",")
                            .map((s) => s.trim())
                            .filter(Boolean);
                          if (!pid || !baseUrl || modelIds.length === 0) {
                            notify("Please enter Provider ID, Base URL, and at least one Model ID.", "err");
                            return;
                          }
                          const parsedHeaders: Record<string, string> = {};
                          entProvHeaders.split("\n").forEach((line) => {
                            const idx = line.indexOf(":");
                            if (idx > 0) {
                              const k = line.slice(0, idx).trim();
                              const v = line.slice(idx + 1).trim();
                              if (k && v) parsedHeaders[k] = v;
                            }
                          });
                          const newProv = {
                            id: pid,
                            name: entProvName.trim() || pid,
                            protocol: "openai_compatible" as const,
                            base_url: baseUrl,
                            api_key_env: entProvApiKeyEnv.trim() || "ENTERPRISE_LLM_API_KEY",
                            headers: Object.keys(parsedHeaders).length > 0 ? parsedHeaders : undefined,
                            models: modelIds.map((m) => ({ id: m, name: m, tier: "coding" })),
                            enabled: true,
                          };
                          const existing = (harnessModels.custom_providers || []).filter((p) => p.id !== pid);
                          const saved = await api.updateHarnessModels({
                            custom_providers: [...existing, newProv],
                          });
                          setHarnessModels(saved);
                          setEntProvBaseUrl("");
                          setEntProvModelsText("");
                          setEntProvHeaders("");
                          if (selectedBlueprint) {
                            const comp = await api.compilePreview(selectedBlueprint.metadata.id, "opencode");
                            setCompiledResult(comp);
                          }
                          notify(
                            `Saved Enterprise Provider '${pid}' (${modelIds.length} model(s))! They are now selectable in OpenCode tier & agent dropdowns.`
                          );
                        }}
                        className="w-full py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs cursor-pointer"
                      >
                        + Save Enterprise OpenAI-Compatible Provider
                      </button>
                    </div>
                  )}

                  {/* Best Practices Reference Card */}
                  <div className="p-3 rounded-xl bg-indigo-950/30 border border-indigo-800/50 space-y-2">
                    <div className="text-[11px] font-bold uppercase tracking-wider text-indigo-300">
                      Multi-Agent Model Routing Best Practices
                    </div>
                    {Object.entries(harnessModels.best_practices || {}).map(([k, advice]) => (
                      <div key={k} className="text-[11px] text-slate-300 leading-relaxed">
                        • {advice}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Panel 2: Two-Way Declarative YAML Editor */}
              {studioRightPanel === "yaml" && (
                <div className="flex-1 flex flex-col p-3 overflow-hidden">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-400">
                      Bidirectional sync with `blueprints/{selectedBlueprint.metadata.id}.yaml`
                    </span>
                    <button
                      onClick={() => handleSaveBlueprint(true)}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold cursor-pointer"
                    >
                      <Save className="w-3.5 h-3.5" /> Apply & Save YAML
                    </button>
                  </div>
                  <textarea
                    value={rawYaml}
                    onChange={(e) => setRawYaml(e.target.value)}
                    className="flex-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-3 font-mono text-xs text-emerald-300 leading-relaxed resize-none focus:outline-none focus:border-indigo-500"
                  />
                </div>
              )}

              {/* Panel 3: Multi-Harness Native Compiler Preview & Exporter */}
              {studioRightPanel === "compiled" && (
                <div className="flex-1 flex flex-col p-3 overflow-y-auto space-y-3 text-xs">
                  <div className="flex items-center gap-1.5 shrink-0">
                    {(["claude_code", "antigravity", "opencode"] as HarnessType[]).map((h) => (
                      <button
                        key={h}
                        onClick={() => {
                          setPreviewHarness(h);
                          setRunHarness(h);
                        }}
                        className={`flex-1 py-1.5 px-2 rounded-lg font-medium border text-[11px] cursor-pointer ${previewHarness === h
                          ? "bg-indigo-600/25 border-indigo-500 text-white"
                          : "bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200"
                          }`}
                      >
                        {HARNESS_LABELS[h].name}
                      </button>
                    ))}
                  </div>

                  {compiledResult && (
                    <>
                      <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 space-y-1 shrink-0">
                        <div className="text-[10px] uppercase font-bold text-slate-400">
                          Headless Invocation Command
                        </div>
                        <div className="font-mono text-[11px] text-cyan-300 break-all">
                          {compiledResult.cli_preview_command}
                        </div>
                      </div>

                      {/* Generated File Tabs */}
                      <div className="space-y-1 shrink-0">
                        <div className="text-[10px] uppercase font-bold text-slate-400">
                          Generated Agent & Configuration Files ({compiledResult.files.length})
                        </div>
                        <div className="flex flex-wrap gap-1 max-h-32 overflow-y-auto p-1 rounded-lg bg-slate-950/60 border border-slate-800/80">
                          {compiledResult.files.map((f, idx) => (
                            <button
                              key={f.relative_path}
                              onClick={() => setSelectedCompiledFileIdx(idx)}
                              className={`px-2 py-1 rounded text-[11px] font-mono border cursor-pointer ${selectedCompiledFileIdx === idx
                                ? "bg-cyan-950 border-cyan-500 text-cyan-200"
                                : "bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200"
                                }`}
                            >
                              {f.relative_path}
                            </button>
                          ))}
                        </div>
                      </div>

                      {compiledResult.files[selectedCompiledFileIdx] && (
                        <div className="flex flex-col shrink-0">
                          <div className="text-[11px] text-slate-400 mb-1">
                            {compiledResult.files[selectedCompiledFileIdx].description}
                          </div>
                          <pre className="h-72 max-h-96 overflow-auto resize-y bg-slate-950 border border-slate-800 rounded-xl p-3 font-mono text-[11px] text-slate-200 leading-relaxed whitespace-pre-wrap">
                            {compiledResult.files[selectedCompiledFileIdx].content}
                          </pre>
                        </div>
                      )}

                      {/* Direct Export & Deployed Project Evaluation */}
                      <div className="pt-3 border-t border-slate-800 space-y-2.5 shrink-0 pb-4">
                        <div className="flex items-center justify-between">
                          <div className="text-[11px] font-semibold text-slate-300">
                            Deploy to Workspace & Link External Docs
                          </div>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-700/50 truncate max-w-[230px]" title={`${selectedBlueprint.metadata.name} (${selectedBlueprint.metadata.id})`}>
                            {selectedBlueprint.metadata.name}
                          </span>
                        </div>
                        <div className="space-y-1.5">
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-0.5">
                              0. Architecture Blueprint to Deploy
                            </label>
                            <select
                              value={selectedBlueprint.metadata.id}
                              onChange={(e) => handleSelectBlueprint(e.target.value)}
                              className="w-full bg-slate-950 border border-indigo-500/60 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-white"
                            >
                              {blueprints.map((b) => {
                                const displayName =
                                  b.metadata.id === selectedBlueprint.metadata.id
                                    ? selectedBlueprint.metadata.name
                                    : b.metadata.name;
                                return (
                                  <option key={b.metadata.id} value={b.metadata.id}>
                                    {displayName} ({b.metadata.id})
                                  </option>
                                );
                              })}
                            </select>
                          </div>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-0.5">
                              1. Target {HARNESS_LABELS[previewHarness].name} Project Workspace Folder
                            </label>
                            <input
                              placeholder={`Target project directory for ${HARNESS_LABELS[previewHarness].name} (e.g. D:\\Projects\\my-app)`}
                              value={exportDir}
                              onChange={(e) => setExportDir(e.target.value)}
                              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-0.5">
                              2. External Reference Documentation Folder (Optional)
                            </label>
                            <input
                              placeholder="Optional: External docs directory (e.g. D:\Projects\my-app\docs)"
                              value={externalDocsDir}
                              onChange={(e) => setExternalDocsDir(e.target.value)}
                              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs font-mono text-emerald-300"
                            />
                          </div>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-0.5">
                              3. Evaluation Benchmark Task (Verifiers used when clicking &ldquo;2. Evaluate Project&rdquo;)
                            </label>
                            <select
                              value={selectedTask?.id || ""}
                              onChange={async (e) => {
                                const res = await api.getTask(e.target.value);
                                setSelectedTask(res.task);
                                setTaskYaml(res.raw_yaml);
                              }}
                              className="w-full bg-slate-950 border border-emerald-500/60 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-emerald-300"
                            >
                              {tasks.map((t) => (
                                <option key={t.id} value={t.id}>
                                  {t.name} ({t.verifiers.length} verifiers)
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={async () => {
                              const targetPath = exportDir.trim() || ".";
                              try {
                                await api.saveBlueprint({ blueprint: selectedBlueprint });
                                const res = await api.exportBlueprint(
                                  selectedBlueprint.metadata.id,
                                  previewHarness,
                                  targetPath,
                                  selectedTask?.id,
                                  externalDocsDir.trim()
                                );
                                setExportDir(res.target_directory);
                                setDeploymentReceipt(res);
                                setRuns(await api.listRuns());
                                notify(
                                  `Deployed ${res.files_written.length} ${HARNESS_LABELS[previewHarness].name} files to ${res.target_directory} with read access to ${res.discovered_docs.length} external docs!`
                                );
                              } catch (err: unknown) {
                                notify(err instanceof Error ? err.message : "Export failed", "err");
                              }
                            }}
                            className="flex-1 flex items-center justify-center gap-1 px-2.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs cursor-pointer"
                            title="Export native agent files, authorize external docs directory, and inject file manifest"
                          >
                            <FolderOutput className="w-3.5 h-3.5" /> 1. Deploy & Link Docs
                          </button>
                          <button
                            onClick={async () => {
                              const targetPath = exportDir.trim() || ".";
                              try {
                                const evaluatedRun = await api.evaluateDeployedDirectory({
                                  project_directory: targetPath,
                                  task_id: selectedTask?.id,
                                  architecture_id: selectedBlueprint.metadata.id,
                                  harness: previewHarness,
                                });
                                setActiveRun(evaluatedRun);
                                setRuns(await api.listRuns());
                                notify(
                                  `Evaluated project folder '${targetPath}'! Score: ${evaluatedRun.evaluation?.overall_composite_score.toFixed(1) ?? "--"
                                  }/100`
                                );
                                setActiveTab("evaluation");
                              } catch (err: unknown) {
                                notify(
                                  err instanceof Error ? err.message : "Failed to evaluate folder",
                                  "err"
                                );
                              }
                            }}
                            className="flex-1 flex items-center justify-center gap-1 px-2.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs cursor-pointer"
                            title="Ingest .harness-eval telemetry & deliverables from the project folder and score performance"
                          >
                            <BarChart3 className="w-3.5 h-3.5" /> 2. Evaluate Project
                          </button>
                        </div>

                        {deploymentReceipt && (
                          <div className="p-2.5 rounded-xl bg-emerald-950/35 border border-emerald-700/50 space-y-1.5 text-[11px]">
                            <div className="font-bold text-emerald-300 flex items-center gap-1">
                              <CheckCircle2 className="w-3.5 h-3.5" /> Deployment & External Docs Verified ({HARNESS_LABELS[previewHarness].name})
                            </div>
                            <div className="text-slate-300">
                              <strong>Agents Installed ({deploymentReceipt.installed_agents.length}):</strong>{" "}
                              <span className="font-mono text-cyan-300">
                                {deploymentReceipt.installed_agents.join(", ")}
                              </span>
                            </div>
                            <div className="text-slate-300">
                              <strong>{previewHarness === "antigravity" ? "Skills Installed:" : "Commands Installed:"}</strong>{" "}
                              <span className="font-mono text-indigo-300">
                                {deploymentReceipt.installed_commands.join(", ")}
                              </span>
                            </div>
                            <div className="text-slate-300">
                              <strong>External Docs Linked ({deploymentReceipt.discovered_docs.length} files):</strong>{" "}
                              <span className="font-mono text-emerald-300">
                                {deploymentReceipt.docs_directory || externalDocsDir || "None"}
                              </span>
                            </div>
                            <div className="text-[10px] text-slate-400 pt-1 border-t border-emerald-800/40">
                              {previewHarness === "antigravity" ? (
                                <>
                                  Next: Open <code className="text-cyan-300">Antigravity (agy)</code> in{" "}
                                  <code className="text-slate-200">{exportDir.trim() || deploymentReceipt.target_directory}</code> and ask:{" "}
                                  <code className="text-emerald-300">
                                    &ldquo;Run the verify-setup skill&rdquo;
                                  </code>{" "}
                                  then{" "}
                                  <code className="text-emerald-300">
                                    &ldquo;Run the generate-tba-pack skill&rdquo;
                                  </code>.
                                </>
                              ) : previewHarness === "opencode" ? (
                                <>
                                  Next: Run <code className="text-cyan-300">opencode agent list</code> or open{" "}
                                  <code className="text-cyan-300">opencode</code> in{" "}
                                  <code className="text-slate-200">{exportDir.trim() || deploymentReceipt.target_directory}</code> and run{" "}
                                  <code className="text-emerald-300">/verify-setup</code> then{" "}
                                  <code className="text-emerald-300">/generate-tba-pack</code>.
                                </>
                              ) : (
                                <>
                                  Next: Open <code className="text-cyan-300">claude</code> in{" "}
                                  <code className="text-slate-200">{exportDir.trim() || deploymentReceipt.target_directory}</code> and run{" "}
                                  <code className="text-emerald-300">/verify-setup</code> then{" "}
                                  <code className="text-emerald-300">/generate-tba-pack</code>.
                                </>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>
              )}
            </aside>
          </div>
        )}

        {/* ==================== TAB 2: BENCHMARK TASKS ==================== */}
        {activeTab === "tasks" && (
          <div className="flex-1 flex overflow-hidden">
            <aside className="w-80 border-r border-slate-800 bg-slate-900/60 p-4 space-y-2.5 overflow-y-auto shrink-0">
              <div className="flex items-center justify-between">
                <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Benchmark Tasks ({tasks.length})
                </div>
                <button
                  onClick={() => setShowNewTaskTemplates((v) => !v)}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-semibold cursor-pointer"
                >
                  <Plus className="w-3 h-3" /> New Task
                </button>
              </div>

              {/* Starter Templates for Different Agentic Designs */}
              {showNewTaskTemplates && (
                <div className="p-2.5 rounded-xl bg-slate-950 border border-emerald-700/60 space-y-1.5">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-300">
                    Create Benchmark Task From Template
                  </div>
                  {[
                    {
                      label: "Frontend / React UI App",
                      template: {
                        id: `ui-benchmark-${Date.now().toString().slice(-4)}`,
                        name: "React UI Feature & Type-Check Benchmark",
                        category: "frontend-ui",
                        difficulty: "medium" as const,
                        description: "Evaluates a coding agent architecture on building React/TypeScript UI components cleanly with zero type or build errors.",
                        prompt: "Implement the requested UI components and verify with `npx tsc -b` and `npm run build`.",
                        workspace_source: exportDir.trim() || ".",
                        expected_subagents: selectedBlueprint ? selectedBlueprint.subagents.map((s) => s.id) : ["planner", "coder", "verifier"],
                        verifiers: [
                          { id: "tsc_check", name: "TypeScript Type-Check (npx tsc -b)", type: "command_exit_code", command: "npx tsc -b", weight: 2.0, required: true, timeout_seconds: 60 },
                          { id: "prod_build", name: "Production Build (npm run build)", type: "command_exit_code", command: "npm run build", weight: 2.0, required: true, timeout_seconds: 90 },
                        ],
                        tags: ["react", "typescript", "frontend-ui"],
                      },
                    },
                    {
                      label: "Python / Backend Code",
                      template: {
                        id: `code-benchmark-${Date.now().toString().slice(-4)}`,
                        name: "Backend Feature & Unit Test Benchmark",
                        category: "feature",
                        difficulty: "medium" as const,
                        description: "Evaluates a multi-agent engineering architecture on implementing backend logic and passing pytest.",
                        prompt: "Implement the requested backend feature, write unit tests, and confirm `pytest -v` passes.",
                        workspace_source: exportDir.trim() || ".",
                        expected_subagents: selectedBlueprint ? selectedBlueprint.subagents.map((s) => s.id) : ["planner", "coder", "verifier"],
                        verifiers: [
                          { id: "pytest_suite", name: "Pytest Suite (pytest -v)", type: "pytest_pass", command: "pytest -v", weight: 2.0, required: true, timeout_seconds: 60 },
                          { id: "diff_limit", name: "Concise Diff (<= 200 lines)", type: "git_diff_max_lines", max_lines: 200, weight: 0.5, required: false, timeout_seconds: 10 },
                        ],
                        tags: ["python", "backend", "pytest"],
                      },
                    },
                    {
                      label: "Technical BA / User Stories (No-Code)",
                      template: {
                        id: `tba-benchmark-${Date.now().toString().slice(-4)}`,
                        name: "Technical BA Delivery Pack (Stories + Workflows)",
                        category: "business-analysis",
                        difficulty: "medium" as const,
                        description: "Evaluates a TBA agent team on producing Connextra/3Cs/INVEST User Stories and Mermaid Process/State Workflows.",
                        prompt: "Analyze all stakeholder requirements and author `WORKFLOWS_AND_DELIVERY_DOCS.md` and `EPICS_AND_USER_STORIES.md`.",
                        workspace_source: exportDir.trim() || ".",
                        expected_subagents: selectedBlueprint ? selectedBlueprint.subagents.map((s) => s.id) : ["requirements_elicitor", "workflow_architect", "user_story_author", "ba_qa_gatekeeper"],
                        verifiers: [
                          { id: "user_story_std", name: "User Story Standard (Connextra + 3Cs + INVEST + BDD)", type: "user_story_invest_check", target_path: "EPICS_AND_USER_STORIES.md", weight: 2.5, required: true, timeout_seconds: 15 },
                          { id: "mermaid_docs", name: "Valid Mermaid Diagrams", type: "mermaid_diagram_valid", target_path: "WORKFLOWS_AND_DELIVERY_DOCS.md", weight: 1.5, required: true, timeout_seconds: 15 },
                        ],
                        tags: ["business-analysis", "no-code", "user-stories"],
                      },
                    },
                    {
                      label: "PM / Meeting Synthesis (No-Code)",
                      template: {
                        id: `pm-benchmark-${Date.now().toString().slice(-4)}`,
                        name: "PM Meeting Notes, Decisions & Action Items Benchmark",
                        category: "product-management",
                        difficulty: "medium" as const,
                        description: "Evaluates a PM / Meeting Orchestrator architecture on synthesizing meeting transcripts into structured decisions, owners, risks, and action items.",
                        prompt: "Synthesize the meeting inputs into `MEETING_SUMMARY.md` with Executive Summary, Decisions, Action Items, Risks, and Next Steps.",
                        workspace_source: exportDir.trim() || ".",
                        expected_subagents: selectedBlueprint ? selectedBlueprint.subagents.map((s) => s.id) : [],
                        verifiers: [
                          { id: "summary_exists", name: "MEETING_SUMMARY.md exists", type: "file_exists", target_path: "MEETING_SUMMARY.md", weight: 1.0, required: true, timeout_seconds: 10 },
                          { id: "pm_sections", name: "Required PM Sections Present", type: "markdown_sections_present", target_path: "MEETING_SUMMARY.md", pattern: "Executive Summary,Decisions,Action Items,Risks,Next Steps", weight: 2.0, required: true, timeout_seconds: 15 },
                        ],
                        tags: ["product-management", "no-code", "meetings"],
                      },
                    },
                    {
                      label: "Blank Custom Task",
                      template: {
                        id: `custom-task-${Date.now().toString().slice(-4)}`,
                        name: "Custom Evaluation Benchmark Task",
                        category: "custom",
                        difficulty: "medium" as const,
                        description: "Custom benchmark task tailored to your agentic architecture.",
                        prompt: "Describe the task goal and expected deliverables here.",
                        workspace_source: exportDir.trim() || ".",
                        expected_subagents: selectedBlueprint ? selectedBlueprint.subagents.map((s) => s.id) : [],
                        verifiers: [
                          { id: "deliverable_check", name: "Primary Deliverable Exists", type: "file_exists", target_path: "README.md", weight: 1.0, required: true, timeout_seconds: 10 },
                        ],
                        tags: ["custom"],
                      },
                    },
                  ].map((item) => (
                    <button
                      key={item.label}
                      onClick={async () => {
                        try {
                          const saved = await api.saveTask({ task: item.template });
                          setSelectedTask(saved.task);
                          setTaskYaml(saved.raw_yaml);
                          setTasks(await api.listTasks());
                          setShowNewTaskTemplates(false);
                          notify(`Created new benchmark task '${saved.task.name}'!`);
                        } catch (err: unknown) {
                          notify(err instanceof Error ? err.message : "Failed to create task", "err");
                        }
                      }}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg bg-slate-900 hover:bg-indigo-950/70 border border-slate-800 hover:border-indigo-500/60 text-[11px] text-slate-200 cursor-pointer"
                    >
                      + {item.label}
                    </button>
                  ))}
                </div>
              )}

              {tasks.map((t) => {
                const isSel = selectedTask?.id === t.id;
                return (
                  <div
                    key={t.id}
                    onClick={async () => {
                      const res = await api.getTask(t.id);
                      setSelectedTask(res.task);
                      setTaskYaml(res.raw_yaml);
                    }}
                    className={`w-full text-left p-3 rounded-xl border transition-all cursor-pointer ${isSel
                      ? "bg-indigo-950/70 border-indigo-500 text-white"
                      : "bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700"
                      }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-semibold text-xs leading-snug">{t.name}</span>
                      <div className="flex items-center gap-0.5 shrink-0">
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            try {
                              const full = await api.getTask(t.id);
                              const cloned: TaskSpec = {
                                ...full.task,
                                id: `${full.task.id}-copy-${Date.now().toString().slice(-3)}`,
                                name: `${full.task.name} (Copy)`,
                              };
                              const saved = await api.saveTask({ task: cloned });
                              setSelectedTask(saved.task);
                              setTaskYaml(saved.raw_yaml);
                              setTasks(await api.listTasks());
                              notify(`Cloned benchmark task '${t.name}'`);
                            } catch (err: unknown) {
                              notify(err instanceof Error ? err.message : "Clone failed", "err");
                            }
                          }}
                          className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-300 cursor-pointer"
                          title="Clone this benchmark task"
                        >
                          <Layers className="w-3 h-3" />
                        </button>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            if (tasks.length <= 1) {
                              notify("Cannot delete the last remaining benchmark task.", "err");
                              return;
                            }
                            try {
                              await api.deleteTask(t.id);
                              const remaining = await api.listTasks();
                              setTasks(remaining);
                              if (isSel && remaining.length > 0) {
                                const next = await api.getTask(remaining[0].id);
                                setSelectedTask(next.task);
                                setTaskYaml(next.raw_yaml);
                              }
                              notify(`Deleted benchmark task '${t.name}'`);
                            } catch (err: unknown) {
                              notify(err instanceof Error ? err.message : "Delete failed", "err");
                            }
                          }}
                          className="p-1 rounded hover:bg-rose-950 text-slate-400 hover:text-rose-400 cursor-pointer"
                          title="Delete this benchmark task"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-1.5 text-[10px]">
                      <span className="px-1.5 py-0.5 rounded bg-slate-800 text-cyan-300 uppercase">
                        {t.category}
                      </span>
                      <span className="px-1.5 py-0.5 rounded bg-slate-800 text-amber-300 uppercase">
                        {t.difficulty}
                      </span>
                      <span className="text-slate-400">{t.verifiers.length} verifiers</span>
                    </div>
                  </div>
                );
              })}
            </aside>

            {selectedTask && (
              <div className="flex-1 grid grid-cols-2 gap-6 p-6 overflow-y-auto">
                <div className="space-y-4">
                  {/* Visual Task Metadata Editor */}
                  <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-indigo-400">
                        Benchmark Task Designer
                      </span>
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={async () => {
                            try {
                              const saved = await api.saveTask({ task: selectedTask });
                              setSelectedTask(saved.task);
                              setTaskYaml(saved.raw_yaml);
                              setTasks(await api.listTasks());
                              notify(`Saved benchmark task '${saved.task.name}'!`);
                            } catch (err: unknown) {
                              notify(err instanceof Error ? err.message : "Save failed", "err");
                            }
                          }}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-semibold cursor-pointer"
                        >
                          <Save className="w-3 h-3" /> Save Task
                        </button>
                        <button
                          onClick={async () => {
                            try {
                              const saved = await api.saveTask({ task: selectedTask });
                              setSelectedTask(saved.task);
                              setTaskYaml(saved.raw_yaml);
                              setTasks(await api.listTasks());
                              setStudioRightPanel("compiled");
                              setActiveTab("studio");
                              notify(`Selected '${saved.task.name}' for Deploy & Evaluate!`);
                            } catch (err: unknown) {
                              notify(err instanceof Error ? err.message : "Save failed", "err");
                            }
                          }}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-semibold cursor-pointer"
                          title="Save this task and open Tab 1 -> Compiled Files ready to click '2. Evaluate Project'"
                        >
                          Use in Deploy &amp; Evaluate <ArrowRight className="w-3 h-3" />
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[10px] text-slate-400 mb-0.5">Task ID (Filename Slug)</label>
                        <input
                          value={selectedTask.id}
                          onChange={(e) =>
                            setSelectedTask({ ...selectedTask, id: e.target.value })
                          }
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 font-mono text-cyan-300"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-400 mb-0.5">Display Title</label>
                        <input
                          value={selectedTask.name}
                          onChange={(e) =>
                            setSelectedTask({ ...selectedTask, name: e.target.value })
                          }
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-white font-semibold"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <label className="block text-[10px] text-slate-400 mb-0.5">Category / Domain</label>
                        <select
                          value={selectedTask.category}
                          onChange={(e) =>
                            setSelectedTask({ ...selectedTask, category: e.target.value })
                          }
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
                        >
                          <option value="frontend-ui">frontend-ui</option>
                          <option value="feature">feature</option>
                          <option value="bugfix">bugfix</option>
                          <option value="refactor">refactor</option>
                          <option value="security">security</option>
                          <option value="test-writing">test-writing</option>
                          <option value="business-analysis">business-analysis</option>
                          <option value="product-management">product-management</option>
                          <option value="consulting">consulting</option>
                          <option value="custom">custom</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-400 mb-0.5">Difficulty</label>
                        <select
                          value={selectedTask.difficulty}
                          onChange={(e) =>
                            setSelectedTask({
                              ...selectedTask,
                              difficulty: e.target.value as "easy" | "medium" | "hard",
                            })
                          }
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
                        >
                          <option value="easy">easy</option>
                          <option value="medium">medium</option>
                          <option value="hard">hard</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-400 mb-0.5">Workspace Source</label>
                        <input
                          value={selectedTask.workspace_source}
                          onChange={(e) =>
                            setSelectedTask({ ...selectedTask, workspace_source: e.target.value })
                          }
                          placeholder="e.g. D:\Projects\my-app"
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 font-mono text-[11px]"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-[10px] text-slate-400 mb-0.5">Description</label>
                      <input
                        value={selectedTask.description}
                        onChange={(e) =>
                          setSelectedTask({ ...selectedTask, description: e.target.value })
                        }
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5"
                      />
                    </div>

                    <div>
                      <div className="flex items-center justify-between mb-0.5">
                        <label className="text-[10px] text-slate-400">
                          Expected Subagents (comma-separated)
                        </label>
                        {selectedBlueprint && (
                          <button
                            onClick={() =>
                              setSelectedTask({
                                ...selectedTask,
                                expected_subagents: selectedBlueprint.subagents.map((s) => s.id),
                              })
                            }
                            className="text-[10px] text-cyan-300 hover:text-cyan-200 cursor-pointer"
                          >
                            Sync from &ldquo;{selectedBlueprint.metadata.name}&rdquo;
                          </button>
                        )}
                      </div>
                      <input
                        value={selectedTask.expected_subagents.join(", ")}
                        onChange={(e) =>
                          setSelectedTask({
                            ...selectedTask,
                            expected_subagents: e.target.value
                              .split(",")
                              .map((s) => s.trim())
                              .filter(Boolean),
                          })
                        }
                        placeholder="e.g. planner, coder, verifier"
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 font-mono text-[11px] text-cyan-200"
                      />
                    </div>

                    <div>
                      <label className="block text-[10px] text-slate-400 mb-0.5">
                        Task Prompt Sent to Harness
                      </label>
                      <textarea
                        rows={4}
                        value={selectedTask.prompt}
                        onChange={(e) =>
                          setSelectedTask({ ...selectedTask, prompt: e.target.value })
                        }
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 font-mono text-[11px] text-slate-200 leading-relaxed"
                      />
                    </div>
                  </div>

                  {/* Deterministic Outcome Verifiers Builder */}
                  <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-bold uppercase text-emerald-400">
                        Deterministic Outcome Verifiers ({selectedTask.verifiers.length})
                      </div>
                      <span className="text-[10px] text-slate-400">
                        Code, UI, BA, PM &amp; Custom Verifiers
                      </span>
                    </div>

                    {/* Quick Add Presets */}
                    <div className="flex flex-wrap gap-1.5 pb-2 border-b border-slate-800">
                      {[
                        {
                          label: "+ npm run build",
                          check: { id: `npm_build_${Date.now().toString().slice(-3)}`, name: "Frontend Production Build (npm run build)", type: "command_exit_code", command: "npm run build", weight: 2.0, required: true, timeout_seconds: 90 },
                        },
                        {
                          label: "+ npx tsc -b",
                          check: { id: `tsc_${Date.now().toString().slice(-3)}`, name: "TypeScript Type-Check (npx tsc -b)", type: "command_exit_code", command: "npx tsc -b", weight: 1.5, required: true, timeout_seconds: 60 },
                        },
                        {
                          label: "+ pytest -v",
                          check: { id: `pytest_${Date.now().toString().slice(-3)}`, name: "Pytest Unit Test Suite", type: "pytest_pass", command: "pytest -v", weight: 2.0, required: true, timeout_seconds: 60 },
                        },
                        {
                          label: "+ User Story (3Cs + INVEST + BDD)",
                          check: { id: `user_story_invest_${Date.now().toString().slice(-3)}`, name: "User Story Standard (3Cs + INVEST + Dev-QA BDD)", type: "user_story_invest_check", target_path: "EPICS_AND_USER_STORIES.md", weight: 2.5, required: true, timeout_seconds: 15 },
                        },
                        {
                          label: "+ Required Markdown Sections",
                          check: { id: `md_sections_${Date.now().toString().slice(-3)}`, name: "Required Specification Sections Present", type: "markdown_sections_present", target_path: "EPICS_AND_USER_STORIES.md", pattern: "Epics,User Stories,Conversation,Confirmation,INVEST,Traceability Matrix", weight: 1.5, required: true, timeout_seconds: 15 },
                        },
                        {
                          label: "+ Mermaid Diagrams",
                          check: { id: `mermaid_valid_${Date.now().toString().slice(-3)}`, name: "Valid Mermaid Process & State Diagrams", type: "mermaid_diagram_valid", target_path: "WORKFLOWS_AND_DELIVERY_DOCS.md", weight: 1.5, required: true, timeout_seconds: 15 },
                        },
                      ].map((btn) => (
                        <button
                          key={btn.label}
                          onClick={async () => {
                            const updatedTask: TaskSpec = {
                              ...selectedTask,
                              verifiers: [...selectedTask.verifiers, btn.check],
                            };
                            const saved = await api.saveTask({ task: updatedTask });
                            setSelectedTask(saved.task);
                            setTaskYaml(saved.raw_yaml);
                            setTasks(await api.listTasks());
                            notify(`Added '${btn.check.name}' verifier`);
                          }}
                          className="px-2 py-1 rounded-lg bg-slate-950 hover:bg-indigo-950 border border-slate-700 hover:border-indigo-500 text-[10px] text-indigo-300 font-medium cursor-pointer"
                        >
                          {btn.label}
                        </button>
                      ))}
                    </div>

                    {/* Custom Verifier CRUD Form (Create & Update) */}
                    <div className={`p-3 rounded-xl bg-slate-950 border space-y-2 text-xs ${editingVerifierId ? "border-cyan-500/70" : "border-slate-800"}`}>
                      <div className="flex items-center justify-between">
                        <div className="text-[10px] font-bold uppercase tracking-wider text-cyan-300">
                          {editingVerifierId ? `Edit Verifier (${editingVerifierId})` : "+ Add Custom Verifier Check"}
                        </div>
                        {editingVerifierId && (
                          <button
                            onClick={() => {
                              setEditingVerifierId(null);
                              setNewVerifierName("");
                              setNewVerifierType("command_exit_code");
                              setNewVerifierCommand("");
                              setNewVerifierTargetPath("");
                              setNewVerifierPattern("");
                              setNewVerifierWeight(1.5);
                              setNewVerifierRequired(true);
                              setNewVerifierMaxLines(150);
                              setNewVerifierTimeout(60);
                            }}
                            className="text-[10px] text-slate-400 hover:text-white cursor-pointer"
                          >
                            Cancel Edit
                          </button>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <input
                          placeholder="Check Name (e.g. Vitest UI Tests)"
                          value={newVerifierName}
                          onChange={(e) => setNewVerifierName(e.target.value)}
                          className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 text-[11px]"
                        />
                        <select
                          value={newVerifierType}
                          onChange={(e) => setNewVerifierType(e.target.value)}
                          className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 font-mono text-[11px] text-cyan-300"
                        >
                          <option value="command_exit_code">command_exit_code (CLI command)</option>
                          <option value="pytest_pass">pytest_pass (pytest)</option>
                          <option value="file_exists">file_exists</option>
                          <option value="file_contains_regex">file_contains_regex</option>
                          <option value="file_not_contains_regex">file_not_contains_regex</option>
                          <option value="markdown_sections_present">markdown_sections_present</option>
                          <option value="user_story_invest_check">user_story_invest_check</option>
                          <option value="mermaid_diagram_valid">mermaid_diagram_valid</option>
                          <option value="git_diff_contains">git_diff_contains</option>
                          <option value="git_diff_max_lines">git_diff_max_lines</option>
                        </select>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        {(newVerifierType === "command_exit_code" || newVerifierType === "pytest_pass") && (
                          <input
                            placeholder="Command (e.g. npm test or pytest -v)"
                            value={newVerifierCommand}
                            onChange={(e) => setNewVerifierCommand(e.target.value)}
                            className="col-span-2 bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 font-mono text-[11px]"
                          />
                        )}
                        {["file_exists", "file_contains_regex", "file_not_contains_regex", "markdown_sections_present", "user_story_invest_check", "mermaid_diagram_valid"].includes(newVerifierType) && (
                          <input
                            placeholder="Target File (e.g. src/App.tsx or MEETING_SUMMARY.md)"
                            value={newVerifierTargetPath}
                            onChange={(e) => setNewVerifierTargetPath(e.target.value)}
                            className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 font-mono text-[11px]"
                          />
                        )}
                        {["file_contains_regex", "file_not_contains_regex", "markdown_sections_present", "git_diff_contains"].includes(newVerifierType) && (
                          <input
                            placeholder="Regex or comma-separated headings"
                            value={newVerifierPattern}
                            onChange={(e) => setNewVerifierPattern(e.target.value)}
                            className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 font-mono text-[11px]"
                          />
                        )}
                        {newVerifierType === "git_diff_max_lines" && (
                          <input
                            type="number"
                            min={10}
                            placeholder="Max changed lines (e.g. 150)"
                            value={newVerifierMaxLines}
                            onChange={(e) => setNewVerifierMaxLines(Number(e.target.value) || 150)}
                            className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 font-mono text-[11px]"
                          />
                        )}
                      </div>
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <div className="flex items-center gap-3 text-[11px] text-slate-300">
                          <label className="flex items-center gap-1">
                            Weight:
                            <input
                              type="number"
                              step="0.5"
                              min="0.5"
                              max="5"
                              value={newVerifierWeight}
                              onChange={(e) => setNewVerifierWeight(Number(e.target.value) || 1)}
                              className="w-14 bg-slate-900 border border-slate-800 rounded px-1.5 py-0.5 font-mono"
                            />
                          </label>
                          <label className="flex items-center gap-1">
                            Timeout(s):
                            <input
                              type="number"
                              min={5}
                              max={300}
                              value={newVerifierTimeout}
                              onChange={(e) => setNewVerifierTimeout(Number(e.target.value) || 60)}
                              className="w-14 bg-slate-900 border border-slate-800 rounded px-1.5 py-0.5 font-mono"
                            />
                          </label>
                          <label className="flex items-center gap-1 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={newVerifierRequired}
                              onChange={(e) => setNewVerifierRequired(e.target.checked)}
                            />
                            Required
                          </label>
                        </div>
                        <button
                          onClick={async () => {
                            const checkId = editingVerifierId || `chk_${Date.now().toString().slice(-4)}`;
                            const builtCheck = {
                              id: checkId,
                              name: newVerifierName.trim() || `${newVerifierType} check`,
                              type: newVerifierType,
                              command: ["command_exit_code", "pytest_pass"].includes(newVerifierType)
                                ? newVerifierCommand.trim() || null
                                : null,
                              target_path: ["file_exists", "file_contains_regex", "file_not_contains_regex", "markdown_sections_present", "user_story_invest_check", "mermaid_diagram_valid"].includes(newVerifierType)
                                ? newVerifierTargetPath.trim() || null
                                : null,
                              pattern: ["file_contains_regex", "file_not_contains_regex", "markdown_sections_present", "git_diff_contains"].includes(newVerifierType)
                                ? newVerifierPattern.trim() || null
                                : null,
                              max_lines: newVerifierType === "git_diff_max_lines" ? newVerifierMaxLines : null,
                              weight: newVerifierWeight,
                              required: newVerifierRequired,
                              timeout_seconds: newVerifierTimeout,
                            };
                            const nextVerifiers = editingVerifierId
                              ? selectedTask.verifiers.map((chk) =>
                                  chk.id === editingVerifierId ? builtCheck : chk
                                )
                              : [...selectedTask.verifiers, builtCheck];
                            const updatedTask: TaskSpec = {
                              ...selectedTask,
                              verifiers: nextVerifiers,
                            };
                            const saved = await api.saveTask({ task: updatedTask });
                            setSelectedTask(saved.task);
                            setTaskYaml(saved.raw_yaml);
                            setTasks(await api.listTasks());
                            const wasEdit = Boolean(editingVerifierId);
                            setEditingVerifierId(null);
                            setNewVerifierName("");
                            setNewVerifierCommand("");
                            setNewVerifierTargetPath("");
                            setNewVerifierPattern("");
                            setNewVerifierWeight(1.5);
                            setNewVerifierRequired(true);
                            setNewVerifierMaxLines(150);
                            setNewVerifierTimeout(60);
                            notify(wasEdit ? `Updated verifier '${builtCheck.name}'` : `Added custom verifier '${builtCheck.name}'`);
                          }}
                          className="px-3 py-1 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-[11px] font-semibold cursor-pointer"
                        >
                          {editingVerifierId ? "Update Verifier" : "+ Add Verifier"}
                        </button>
                      </div>
                    </div>

                    {/* Active Verifiers List */}
                    <div className="space-y-2">
                      {selectedTask.verifiers.map((v) => (
                        <div
                          key={v.id}
                          className={`p-2.5 rounded-lg bg-slate-950 border flex items-center justify-between gap-2 text-xs ${
                            editingVerifierId === v.id ? "border-cyan-500" : "border-slate-800"
                          }`}
                        >
                          <div className="min-w-0">
                            <div className="font-semibold text-white flex items-center gap-1.5">
                              <span>{v.name}</span>
                              {v.required && (
                                <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-950 text-amber-300 border border-amber-800/50 uppercase">
                                  Req
                                </span>
                              )}
                            </div>
                            <div className="font-mono text-[11px] text-slate-400 truncate">
                              type: {v.type}{" "}
                              {v.target_path ? `| file: ${v.target_path} ` : ""}
                              {v.command ? `| cmd: ${v.command}` : v.pattern ? `| pattern: ${v.pattern}` : v.max_lines ? `| max_lines: ${v.max_lines}` : ""}
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            <span className="text-[11px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-700/40">
                              {v.weight}x
                            </span>
                            <button
                              onClick={() => {
                                setEditingVerifierId(v.id);
                                setNewVerifierName(v.name);
                                setNewVerifierType(v.type);
                                setNewVerifierCommand(v.command || "");
                                setNewVerifierTargetPath(v.target_path || "");
                                setNewVerifierPattern(v.pattern || "");
                                setNewVerifierMaxLines(v.max_lines || 150);
                                setNewVerifierWeight(v.weight);
                                setNewVerifierRequired(v.required);
                                setNewVerifierTimeout(v.timeout_seconds || 60);
                              }}
                              className="p-1 text-slate-400 hover:text-cyan-300 cursor-pointer"
                              title="Edit verifier"
                            >
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={async () => {
                                const updatedTask: TaskSpec = {
                                  ...selectedTask,
                                  verifiers: selectedTask.verifiers.filter((chk) => chk.id !== v.id),
                                };
                                const saved = await api.saveTask({ task: updatedTask });
                                setSelectedTask(saved.task);
                                setTaskYaml(saved.raw_yaml);
                                setTasks(await api.listTasks());
                                if (editingVerifierId === v.id) {
                                  setEditingVerifierId(null);
                                }
                                notify(`Removed verifier '${v.name}'`);
                              }}
                              className="p-1 text-slate-500 hover:text-rose-400 cursor-pointer"
                              title="Remove verifier"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex flex-col">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold uppercase text-slate-400">
                      Task Specification YAML (`tasks/{selectedTask.id}.yaml`)
                    </span>
                    <button
                      onClick={async () => {
                        try {
                          const saved = await api.saveTask({ raw_yaml: taskYaml });
                          setSelectedTask(saved.task);
                          setTaskYaml(saved.raw_yaml);
                          setTasks(await api.listTasks());
                          notify(`Saved task '${saved.task.name}'`);
                        } catch (err: unknown) {
                          notify(err instanceof Error ? err.message : "Failed to save task", "err");
                        }
                      }}
                      className="flex items-center gap-1 px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold cursor-pointer"
                    >
                      <Save className="w-3.5 h-3.5" /> Save Task YAML
                    </button>
                  </div>
                  <textarea
                    value={taskYaml}
                    onChange={(e) => setTaskYaml(e.target.value)}
                    className="flex-1 bg-slate-900 border border-slate-800 rounded-xl p-4 font-mono text-xs text-cyan-300 resize-none"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* ==================== TAB 3: EXECUTE & LIVE TRACE ==================== */}
        {activeTab === "runner" && (
          <div className="flex-1 flex overflow-hidden">
            {/* Left Launchpad & Run History */}
            <aside className="w-80 border-r border-slate-800 bg-slate-900/60 p-4 flex flex-col gap-4 overflow-y-auto shrink-0">
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-bold uppercase tracking-wider text-indigo-400">
                    Launch Isolated Sandbox Run
                  </div>
                  {isRunBlocking && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/40 text-amber-300 text-[10px] font-bold uppercase">
                      <Loader2 className="w-2.5 h-2.5 animate-spin" /> Locked
                    </span>
                  )}
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Architecture Blueprint</label>
                  <select
                    value={selectedBlueprint?.metadata.id || ""}
                    disabled={isRunBlocking}
                    onChange={(e) => handleSelectBlueprint(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {blueprints.map((b) => (
                      <option key={b.metadata.id} value={b.metadata.id}>
                        {b.metadata.name} (v{b.metadata.version})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Benchmark Task</label>
                  <select
                    value={selectedTask?.id || ""}
                    disabled={isRunBlocking}
                    onChange={async (e) => {
                      const res = await api.getTask(e.target.value);
                      setSelectedTask(res.task);
                      setTaskYaml(res.raw_yaml);
                    }}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {tasks.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name} ({t.difficulty})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Target Coding Harness</label>
                  <select
                    value={runHarness}
                    disabled={isRunBlocking}
                    onChange={(e) => setRunHarness(e.target.value as HarnessType)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <option value="claude_code">
                      Claude Code ({harnessStatus.claude_code?.available ? "CLI Detected" : "Sandbox Sim Ready"})
                    </option>
                    <option value="antigravity">
                      Antigravity ({harnessStatus.antigravity?.available ? "CLI Detected" : "Sandbox Sim Ready"})
                    </option>
                    <option value="opencode">
                      OpenCode ({harnessStatus.opencode?.available ? "CLI Detected" : "Sandbox Sim Ready"})
                    </option>
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Execution Mode</label>
                  <select
                    value={runMode}
                    disabled={isRunBlocking}
                    onChange={(e) => setRunMode(e.target.value as RunMode)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <option value="simulated_benchmark">
                      Simulated Sandbox Benchmark (Fast Topology Test)
                    </option>
                    <option value="headless">
                      Headless Automated Harness CLI (claude -p / opencode run / agy)
                    </option>
                    <option value="interactive">
                      Interactive User Session (Deploy to Sandbox + Live Hooks)
                    </option>
                  </select>
                </div>

                {/* Preliminary Pre-Flight Checks Panel */}
                <div className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-200">
                      <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
                      Pre-Flight Checks
                      {preflight && (
                        <span
                          className={`px-1.5 py-0.2 rounded text-[9px] font-bold uppercase ${
                            preflight.ready
                              ? "bg-emerald-950 text-emerald-300 border border-emerald-700/50"
                              : "bg-rose-950 text-rose-300 border border-rose-700/50"
                          }`}
                        >
                          {preflight.ready ? "Ready" : "Blocked"}
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => refreshPreflight()}
                      disabled={isCheckingPreflight}
                      className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-cyan-300 cursor-pointer disabled:opacity-50"
                      title="Re-run preliminary checks"
                    >
                      <RefreshCw className={`w-3 h-3 ${isCheckingPreflight ? "animate-spin" : ""}`} />
                      Re-check
                    </button>
                  </div>
                  {preflight ? (
                    <div className="space-y-1">
                      {preflight.checks.map((chk) => (
                        <div key={chk.id} className="flex items-start gap-1.5 text-[10px] leading-snug">
                          {chk.status === "pass" ? (
                            <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0 mt-0.5" />
                          ) : chk.status === "warn" ? (
                            <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0 mt-0.5" />
                          ) : (
                            <XCircle className="w-3 h-3 text-rose-400 shrink-0 mt-0.5" />
                          )}
                          <div className="min-w-0">
                            <span
                              className={
                                chk.status === "fail"
                                  ? "text-rose-300 font-semibold"
                                  : chk.status === "warn"
                                    ? "text-amber-200"
                                    : "text-slate-300"
                              }
                            >
                              {chk.message}
                            </span>
                            {chk.detail && (
                              <div className="text-[9px] text-slate-500 break-words">{chk.detail}</div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-[10px] text-slate-500">Checking environment readiness...</div>
                  )}
                </div>

                <button
                  onClick={handleStartRun}
                  disabled={isRunBlocking || (preflight !== null && !preflight.ready)}
                  className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-400 disabled:cursor-not-allowed text-white font-semibold text-xs cursor-pointer"
                >
                  {isRunBlocking ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Play className="w-3.5 h-3.5 fill-current" />
                  )}
                  {isLaunchingRun
                    ? "Running Pre-Flight & Deploying..."
                    : runningRun
                      ? runningRun.status === "evaluating"
                        ? "Evaluating in Progress (Blocked)..."
                        : "Execution Running (Blocked)..."
                      : preflight && !preflight.ready
                        ? "Fix Pre-Flight Checks to Run"
                        : "Start Execution Run"}
                </button>
              </div>

              {/* Run History List */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-1">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Execution History ({runs.length})
                  </div>
                  {runs.length > 0 && (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={handleClearStaleRuns}
                        disabled={isRunBlocking || isClearingStale}
                        className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-950/70 hover:bg-amber-900 border border-amber-800/60 text-amber-300 text-[10px] font-semibold cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                        title="Clear stale, interrupted, or orphaned evaluations"
                      >
                        <RefreshCw className={`w-2.5 h-2.5 ${isClearingStale ? "animate-spin" : ""}`} />
                        Clear Stale
                      </button>
                      <button
                        disabled={isRunBlocking}
                        onClick={async () => {
                          try {
                            const res = await api.deleteAllRuns();
                            setRuns([]);
                            setActiveRun(null);
                            setTelemetryEvents([]);
                            setPlainTextLog("");
                            setCompareIds([]);
                            notify(`Cleared all ${res.deleted_count} execution run(s) from history`);
                            await refreshPreflight();
                          } catch (err: unknown) {
                            notify(err instanceof Error ? err.message : "Failed to clear history", "err");
                          }
                        }}
                        className="flex items-center gap-1 px-2 py-0.5 rounded bg-rose-950/70 hover:bg-rose-900 border border-rose-800/60 text-rose-300 text-[10px] font-semibold cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                        title="Delete all execution history"
                      >
                        <Trash2 className="w-3 h-3" /> Clear All
                      </button>
                    </div>
                  )}
                </div>
                {runs.map((r) => (
                  <div
                    key={r.id}
                    onClick={() => setActiveRun(r)}
                    className={`w-full text-left p-2.5 rounded-xl border text-xs transition-all cursor-pointer group relative ${activeRun?.id === r.id
                      ? "bg-indigo-950/70 border-indigo-500 text-white"
                      : "bg-slate-900/90 border-slate-800 text-slate-300 hover:border-slate-700"
                      }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold truncate">{r.architecture_name}</span>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {r.evaluation && (
                          <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-700/40">
                            {r.evaluation.overall_composite_score.toFixed(1)}
                          </span>
                        )}
                        {isRunStale(r) && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-950/80 text-amber-300 border border-amber-700/50 uppercase font-bold">
                            Stale
                          </span>
                        )}
                        <button
                          disabled={isRunBlocking && isRunStatusActive(r.status)}
                          onClick={async (e) => {
                            e.stopPropagation();
                            try {
                              const res = await api.deleteRun(r.id);
                              const remaining = runs.filter((item) => item.id !== r.id);
                              setRuns(remaining);
                              setCompareIds((prev) => prev.filter((id) => id !== r.id));
                              if (activeRun?.id === r.id) {
                                setActiveRun(remaining[0] || null);
                                if (!remaining[0]) {
                                  setTelemetryEvents([]);
                                  setPlainTextLog("");
                                }
                              }
                              notify(
                                res.already_missing
                                  ? `Cleared stale entry ${r.id} (already removed on server)`
                                  : `Deleted run ${r.id}`
                              );
                              await refreshPreflight();
                            } catch (err: unknown) {
                              const msg = err instanceof Error ? err.message : "";
                              if (msg.toLowerCase().includes("not found") || msg.includes("404")) {
                                const remaining = runs.filter((item) => item.id !== r.id);
                                setRuns(remaining);
                                setCompareIds((prev) => prev.filter((id) => id !== r.id));
                                if (activeRun?.id === r.id) {
                                  setActiveRun(remaining[0] || null);
                                  if (!remaining[0]) {
                                    setTelemetryEvents([]);
                                    setPlainTextLog("");
                                  }
                                }
                                notify(`Cleared stale entry ${r.id}`);
                              } else {
                                notify(msg || "Failed to delete run", "err");
                              }
                            }
                          }}
                          className="p-1 rounded hover:bg-rose-950 text-slate-500 hover:text-rose-400 transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                          title={
                            isRunStatusActive(r.status)
                              ? "Stop this run before deleting"
                              : `Delete run ${r.id}`
                          }
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                    <div className="text-[11px] text-slate-400 truncate mt-0.5">{r.task_name}</div>
                    <div className="flex items-center justify-between mt-1.5 text-[10px] text-slate-400">
                      <span className="px-1.5 py-0.5 rounded bg-slate-800 text-cyan-300">{r.harness}</span>
                      <span
                        className={`uppercase font-semibold ${r.status === "completed"
                          ? "text-emerald-400"
                          : isRunStatusActive(r.status)
                            ? "text-amber-300 animate-pulse"
                            : r.status === "failed"
                              ? "text-rose-400"
                              : "text-slate-400"
                          }`}
                      >
                        {r.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </aside>

            {/* Right: Live Topology Execution & Telemetry Stream */}
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Blocking Execution Status Banner */}
              {isRunBlocking && (
                <div className="px-4 py-2.5 bg-amber-950/80 border-b border-amber-700/70 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2.5 text-xs text-amber-100">
                    <Loader2 className="w-4 h-4 text-amber-400 animate-spin shrink-0" />
                    <div>
                      <span className="font-bold text-amber-300 uppercase tracking-wide">
                        Blocking Evaluation In Progress
                      </span>{" "}
                      —{" "}
                      {runningRun ? (
                        <>
                          <span className="font-mono text-amber-200">{runningRun.id}</span> (
                          <span className="uppercase font-semibold">{runningRun.status}</span>)
                          {" • "}New runs are locked until this evaluation completes or is stopped.
                        </>
                      ) : (
                        "Running pre-flight checks and preparing isolated Git sandbox..."
                      )}
                    </div>
                  </div>
                  {runningRun && (
                    <button
                      onClick={() => handleStopActiveRun(runningRun.id)}
                      disabled={isStoppingRun}
                      className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-semibold text-xs shrink-0 cursor-pointer"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      {isStoppingRun ? "Stopping..." : "Stop & Evaluate Now"}
                    </button>
                  )}
                </div>
              )}

              {activeRun ? (
                <>
                  <div className="p-4 border-b border-slate-800 bg-slate-900/70 flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-white">
                          {activeRun.architecture_name}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-700/40">
                          {activeRun.harness}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                          {activeRun.mode}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono mt-1">
                        Sandbox: {activeRun.sandbox_path}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {isRunStatusActive(activeRun.status) && (
                        <button
                          onClick={() => handleStopActiveRun(activeRun.id)}
                          disabled={isStoppingRun}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-semibold text-xs cursor-pointer"
                        >
                          <XCircle className="w-3.5 h-3.5" />
                          {isStoppingRun ? "Stopping..." : "Stop & Evaluate Now"}
                        </button>
                      )}
                      {activeRun.status === "waiting_for_user" && (
                        <button
                          onClick={handleCompleteInteractive}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs cursor-pointer"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Complete & Evaluate Interactive Session
                        </button>
                      )}
                      {activeRun.evaluation && (
                        <button
                          onClick={() => setActiveTab("evaluation")}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs cursor-pointer"
                        >
                          <BarChart3 className="w-3.5 h-3.5" />
                          View Full Evaluation ({activeRun.evaluation.overall_composite_score.toFixed(1)}/100)
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Interactive Session Instructions Banner */}
                  {activeRun.status === "waiting_for_user" && (
                    <div className="p-3 bg-amber-950/60 border-b border-amber-800/70 text-xs text-amber-200 flex items-center justify-between">
                      <div>
                        <span className="font-bold">Interactive Session Ready:</span> Open a terminal in the isolated worktree and run:{" "}
                        <code className="px-2 py-0.5 rounded bg-slate-950 text-cyan-300 font-mono">
                          cd "{activeRun.sandbox_path}" && {activeRun.cli_command}
                        </code>
                      </div>
                    </div>
                  )}

                  {/* Telemetry Event Timeline & Copyable Console Log */}
                  <div className="flex-1 overflow-y-auto p-4 space-y-3">
                    {/* Live Status & Controls Bar */}
                    <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between gap-4 flex-wrap">
                      <div className="flex items-center gap-3 text-xs">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full font-bold uppercase text-[10px] ${activeRun.status === "running"
                            ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse"
                            : activeRun.status === "completed"
                              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                              : activeRun.status === "failed"
                                ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                                : "bg-indigo-500/20 text-indigo-300 border border-indigo-500/40"
                            }`}
                        >
                          <Activity className="w-3 h-3" />
                          {activeRun.status}
                        </span>
                        <span className="text-slate-300">
                          Active Node:{" "}
                          <strong className="text-cyan-300 font-mono">
                            @{activeAgentNode || "root_orchestrator"}
                          </strong>
                        </span>
                        <span className="text-slate-400">•</span>
                        <span className="text-slate-400">{telemetryEvents.length} coalesced steps</span>
                      </div>

                      <div className="flex items-center gap-2">
                        <div className="flex bg-slate-950 p-0.5 rounded-lg border border-slate-800 text-[11px]">
                          <button
                            onClick={() => setTraceViewMode("cards")}
                            className={`px-2.5 py-1 rounded-md font-medium cursor-pointer ${traceViewMode === "cards"
                              ? "bg-indigo-600 text-white"
                              : "text-slate-400 hover:text-slate-200"
                              }`}
                          >
                            Structured Timeline
                          </button>
                          <button
                            onClick={async () => {
                              setTraceViewMode("console_log");
                              const res = await api.getRunLog(activeRun.id);
                              setPlainTextLog(res.log);
                            }}
                            className={`px-2.5 py-1 rounded-md font-medium cursor-pointer ${traceViewMode === "console_log"
                              ? "bg-indigo-600 text-white"
                              : "text-slate-400 hover:text-slate-200"
                              }`}
                          >
                            Plain-Text Log (execution.log)
                          </button>
                        </div>

                        <button
                          onClick={async () => {
                            const res = await api.getRunLog(activeRun.id);
                            setPlainTextLog(res.log);
                            await navigator.clipboard.writeText(res.log);
                            notify("Copied clean execution log to clipboard — paste it directly in chat for feedback!");
                          }}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-cyan-300 text-xs font-semibold cursor-pointer"
                        >
                          <Code2 className="w-3.5 h-3.5" />
                          Copy Log for Feedback
                        </button>
                      </div>
                    </div>

                    {traceViewMode === "console_log" ? (
                      <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-emerald-300 whitespace-pre-wrap leading-relaxed overflow-x-auto">
                        {plainTextLog || "Loading formatted execution log..."}
                      </pre>
                    ) : (
                      telemetryEvents.map((ev, idx) => (
                        <div
                          key={ev.id || idx}
                          className={`p-3.5 rounded-xl border text-xs flex items-start justify-between gap-4 ${ev.status === "blocked" || ev.event_type === "TopologyViolation"
                            ? "bg-rose-950/40 border-rose-700/70"
                            : ev.event_type === "SubagentStart"
                              ? "bg-cyan-950/35 border-cyan-700/60"
                              : "bg-slate-900/90 border-slate-800"
                            }`}
                        >
                          <div className="space-y-1.5 min-w-0 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800">
                                #{idx + 1}
                              </span>
                              <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-slate-800 text-indigo-300 font-semibold">
                                {ev.event_type}
                              </span>
                              <span className="font-semibold text-cyan-300">@{ev.agent_id}</span>
                              {ev.tool_name && (
                                <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-slate-950 text-emerald-300 border border-slate-800">
                                  tool: {ev.tool_name}
                                </span>
                              )}
                              <span className="text-[10px] text-slate-500">
                                {ev.timestamp.slice(11, 19)}
                              </span>
                            </div>
                            {ev.message && (
                              <div className="text-slate-200 leading-relaxed whitespace-pre-wrap">
                                {ev.message}
                              </div>
                            )}
                            {ev.tool_output && (
                              <pre className="mt-1 p-2.5 rounded-lg bg-slate-950 text-[11px] font-mono text-slate-300 overflow-x-auto border border-slate-800">
                                {ev.tool_output}
                              </pre>
                            )}
                          </div>
                          <div className="text-right font-mono text-[11px] text-slate-400 shrink-0 space-y-0.5">
                            {(ev.input_tokens > 0 || ev.output_tokens > 0) && (
                              <div className="text-slate-300">
                                {(ev.input_tokens + ev.output_tokens).toLocaleString()} tok ($
                                {ev.cost_usd.toFixed(4)})
                              </div>
                            )}
                            {ev.duration_ms > 0 && <div>{ev.duration_ms.toFixed(0)} ms</div>}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </>
              ) : (
                <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
                  Select or start an execution run on the left to stream live telemetry.
                </div>
              )}
            </div>
          </div>
        )}

        {/* ==================== TAB 4: 4-LAYER EVALUATION SCORECARD ==================== */}
        {activeTab === "evaluation" && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {activeRun?.evaluation ? (
              <>
                {/* Top Summary KPI Cards */}
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                      {activeRun.evaluation.architecture_name}
                      <span className="text-xs px-2.5 py-1 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                        {activeRun.evaluation.harness}
                      </span>
                    </h2>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Task: {activeRun.evaluation.task_name} • Run ID: {activeRun.id}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        setActiveTab("advisor");
                        handleLoadAdvisor(false);
                      }}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white font-semibold text-xs shadow-md cursor-pointer"
                    >
                      <Wand2 className="w-4 h-4" />
                      Diagnose with AI Architecture Advisor
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-5 gap-4">
                  {[
                    {
                      label: "Overall Composite Score",
                      val: `${activeRun.evaluation.overall_composite_score.toFixed(1)} / 100`,
                      sub: "Weighted 4-Layer Index",
                      color: "text-emerald-400",
                    },
                    {
                      label: "Layer 1: Deterministic Tests",
                      val: `${activeRun.evaluation.deterministic_score.toFixed(1)}%`,
                      sub: activeRun.evaluation.all_required_verifiers_passed
                        ? "All Required Checks Passed"
                        : "Required Check Failed",
                      color: activeRun.evaluation.all_required_verifiers_passed
                        ? "text-cyan-400"
                        : "text-rose-400",
                    },
                    {
                      label: "Layer 2: Topology Adherence",
                      val: `${activeRun.evaluation.topology_adherence_pct.toFixed(1)}%`,
                      sub: `${activeRun.evaluation.trajectory.handoffs_count} Handoffs • ${activeRun.evaluation.trajectory.topology_violations_blocked} Blocked`,
                      color: "text-indigo-400",
                    },
                    {
                      label: "Layer 3: LLM-as-a-Judge",
                      val: `${activeRun.evaluation.judge_score.toFixed(1)} / 100`,
                      sub: `Provider: ${activeRun.evaluation.judge.provider_used}`,
                      color: "text-purple-400",
                    },
                    {
                      label: "Total Tokens & Cost",
                      val: `$${activeRun.evaluation.trajectory.total_cost_usd.toFixed(4)}`,
                      sub: `${activeRun.evaluation.trajectory.total_tokens.toLocaleString()} tokens • ${activeRun.evaluation.trajectory.total_duration_ms.toFixed(0)} ms`,
                      color: "text-amber-300",
                    },
                  ].map((card) => (
                    <div
                      key={card.label}
                      className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-1"
                    >
                      <div className="text-[11px] text-slate-400 font-medium">{card.label}</div>
                      <div className={`text-2xl font-bold ${card.color}`}>{card.val}</div>
                      <div className="text-[11px] text-slate-500">{card.sub}</div>
                    </div>
                  ))}
                </div>

                <div className="grid grid-cols-2 gap-6">
                  {/* Per-Node / Per-Subagent Resource & Token Breakdown */}
                  <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
                    <div className="text-sm font-bold text-white flex items-center justify-between">
                      <span>Per-Node Architecture Breakdown (Orchestrator vs Subagents)</span>
                      <span className="text-xs font-normal text-slate-400">
                        Token & Latency Distribution
                      </span>
                    </div>
                    <div className="space-y-3">
                      {activeRun.evaluation.trajectory.per_node_breakdown.map((node) => (
                        <div
                          key={node.node_id}
                          className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2 text-xs"
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <span className="font-bold text-white">{node.node_name}</span>{" "}
                              <span className="font-mono text-cyan-400">({node.node_id})</span>
                            </div>
                            <div className="font-mono text-slate-300">
                              {node.total_tokens.toLocaleString()} tok ({node.token_share_pct}%) • $
                              {node.cost_usd.toFixed(4)} • {node.duration_ms.toFixed(0)} ms
                            </div>
                          </div>
                          {/* Token Share Bar */}
                          <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-indigo-500 to-cyan-400"
                              style={{ width: `${Math.max(4, node.token_share_pct)}%` }}
                            />
                          </div>
                          <div className="flex items-center gap-4 text-[11px] text-slate-400">
                            <span>Invocations: {node.invocations}</span>
                            <span>Tool Calls: {node.tool_calls}</span>
                            <span>Failed Tools: {node.failed_tool_calls}</span>
                            <span>Guardrail Blocks: {node.blocked_tool_calls}</span>
                          </div>
                        </div>
                      ))}
                    </div>

                    {activeRun.evaluation.trajectory.bottleneck_warnings.length > 0 && (
                      <div className="p-3 rounded-xl bg-amber-950/50 border border-amber-800/60 space-y-1">
                        <div className="text-xs font-bold text-amber-300 flex items-center gap-1.5">
                          <AlertTriangle className="w-3.5 h-3.5" /> Architecture Bottleneck Diagnostics
                        </div>
                        {activeRun.evaluation.trajectory.bottleneck_warnings.map((w, i) => (
                          <div key={i} className="text-xs text-amber-200/90">
                            • {w}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Layer 1 Deterministic Verifiers & Layer 3 Judge Rubric */}
                  <div className="space-y-6">
                    <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
                      <div className="text-sm font-bold text-white">
                        Layer 1: Deterministic Outcome Verifiers
                      </div>
                      {activeRun.evaluation.verifier_results.map((vr) => (
                        <div
                          key={vr.check_id}
                          className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5 text-xs"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-white flex items-center gap-1.5">
                              {vr.passed ? (
                                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                              ) : (
                                <XCircle className="w-4 h-4 text-rose-400" />
                              )}
                              {vr.name}
                            </span>
                            <span className="font-mono text-[11px] text-slate-400">
                              {vr.duration_ms.toFixed(0)} ms
                            </span>
                          </div>
                          {vr.output && (
                            <pre className="p-2 rounded bg-slate-900 font-mono text-[11px] text-slate-300 overflow-x-auto max-h-36">
                              {vr.output}
                            </pre>
                          )}
                        </div>
                      ))}
                    </div>

                    <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
                      <div className="text-sm font-bold text-white">
                        Layer 3: Rubric Evaluation & Human Rating
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">
                        {activeRun.evaluation.judge.executive_summary}
                      </p>
                      <div className="space-y-2">
                        {activeRun.evaluation.judge.dimension_scores.map((d) => (
                          <div
                            key={d.dimension_id}
                            className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-xs"
                          >
                            <div className="flex items-center justify-between font-semibold">
                              <span>{d.name}</span>
                              <span className="text-indigo-300 font-mono">{d.score.toFixed(1)} / 5.0</span>
                            </div>
                            <div className="text-slate-400 text-[11px] mt-1">{d.rationale}</div>
                          </div>
                        ))}
                      </div>

                      {/* Human Annotation Form */}
                      <div className="pt-3 border-t border-slate-800 flex items-center gap-2 text-xs">
                        <select
                          value={humanRating}
                          onChange={(e) => setHumanRating(Number(e.target.value))}
                          className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
                        >
                          <option value={5}>★★★★★ (5/5)</option>
                          <option value={4}>★★★★☆ (4/5)</option>
                          <option value={3}>★★★☆☆ (3/5)</option>
                          <option value={2}>★★☆☆☆ (2/5)</option>
                          <option value={1}>★☆☆☆☆ (1/5)</option>
                        </select>
                        <input
                          placeholder="Add human review notes..."
                          value={humanNotes}
                          onChange={(e) => setHumanNotes(e.target.value)}
                          className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5"
                        />
                        <button
                          onClick={async () => {
                            const updatedEval = await api.saveHumanGrade(
                              activeRun.id,
                              humanRating,
                              humanNotes
                            );
                            setActiveRun({ ...activeRun, evaluation: updatedEval });
                            notify("Saved human rating & review annotation");
                          }}
                          className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold cursor-pointer"
                        >
                          Save Grade
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Sandbox Git Diff Viewer */}
                <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-2">
                  <div className="text-sm font-bold text-white">
                    Captured Sandbox Git Diff ({activeRun.evaluation.changed_files.join(", ") || "no files"})
                  </div>
                  <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-emerald-300 overflow-x-auto">
                    {activeRun.evaluation.git_diff || "No task files modified."}
                  </pre>
                </div>
              </>
            ) : (
              <div className="text-center py-20 text-slate-400">
                Execute a run first to inspect its 4-Layer Evaluation Scorecard.
              </div>
            )}
          </div>
        )}

        {/* ==================== TAB 5: SIDE-BY-SIDE A/B COMPARISON MATRIX ==================== */}
        {activeTab === "compare" && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-white">
                  Side-by-Side Architecture & Cross-Harness A/B Matrix
                </h2>
                <p className="text-xs text-slate-400">
                  Select 2 or more runs below to compare Composite Scores, Per-Node Tokens, Latency, and Handoff Adherence
                </p>
              </div>
              <button
                onClick={handleRunComparison}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Recompute A/B Matrix
              </button>
            </div>

            {/* Run Multi-Selector */}
            <div className="flex flex-wrap gap-2">
              {runs.map((r) => {
                const checked = compareIds.includes(r.id);
                return (
                  <button
                    key={r.id}
                    onClick={() => {
                      const next = checked
                        ? compareIds.filter((id) => id !== r.id)
                        : [...compareIds, r.id];
                      setCompareIds(next);
                    }}
                    className={`px-3 py-1.5 rounded-xl border text-xs font-medium flex items-center gap-2 cursor-pointer ${checked
                      ? "bg-indigo-950 border-indigo-500 text-white"
                      : "bg-slate-900 border-slate-800 text-slate-400"
                      }`}
                  >
                    <input type="checkbox" checked={checked} readOnly />
                    <span>{r.architecture_name}</span>
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-cyan-300">
                      {r.harness}
                    </span>
                    <span className="text-[10px] text-slate-400">({r.task_id})</span>
                  </button>
                );
              })}
            </div>

            {abResult && abResult.runs.length > 0 && (
              <>
                {/* Key Takeaways Banner */}
                <div className="p-4 rounded-2xl bg-indigo-950/40 border border-indigo-700/50 space-y-1.5">
                  <div className="text-xs font-bold uppercase tracking-wider text-indigo-300">
                    Automated A/B Benchmark Takeaways
                  </div>
                  {abResult.key_takeaways.map((tk, i) => (
                    <div key={i} className="text-xs text-slate-200">
                      • {tk}
                    </div>
                  ))}
                </div>

                {/* Comparison Table */}
                <div className="overflow-x-auto rounded-2xl border border-slate-800 bg-slate-900">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950/80 text-slate-400 uppercase text-[11px]">
                      <tr>
                        <th className="p-3.5">Metric / Dimension</th>
                        {abResult.runs.map((r) => (
                          <th key={r.id} className="p-3.5 border-l border-slate-800">
                            <div className="font-bold text-white text-xs flex items-center gap-1.5">
                              {r.architecture_name}
                              {abResult.winner_run_id === r.id && (
                                <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-[10px]">
                                  WINNER
                                </span>
                              )}
                            </div>
                            <div className="text-[10px] text-cyan-400 mt-0.5">
                              Harness: {r.harness} • Task: {r.task_id}
                            </div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {[
                        {
                          label: "Overall Composite Score",
                          render: (r: RunRecord) =>
                            `${r.evaluation?.overall_composite_score.toFixed(1) ?? "--"} / 100`,
                          highlight: true,
                        },
                        {
                          label: "Deterministic Verifiers Score",
                          render: (r: RunRecord) => `${r.evaluation?.deterministic_score.toFixed(1) ?? "--"}%`,
                        },
                        {
                          label: "Topology Adherence",
                          render: (r: RunRecord) =>
                            `${r.evaluation?.topology_adherence_pct.toFixed(1) ?? "--"}%`,
                        },
                        {
                          label: "Tool & Turn Efficiency",
                          render: (r: RunRecord) => `${r.evaluation?.efficiency_pct.toFixed(1) ?? "--"}%`,
                        },
                        {
                          label: "LLM-as-a-Judge Rubric Score",
                          render: (r: RunRecord) => `${r.evaluation?.judge_score.toFixed(1) ?? "--"} / 100`,
                        },
                        {
                          label: "Total Tokens Consumed",
                          render: (r: RunRecord) =>
                            r.evaluation?.trajectory.total_tokens.toLocaleString() ?? "--",
                        },
                        {
                          label: "Estimated Session Cost (USD)",
                          render: (r: RunRecord) =>
                            `$${r.evaluation?.trajectory.total_cost_usd.toFixed(4) ?? "--"}`,
                        },
                        {
                          label: "Execution Duration",
                          render: (r: RunRecord) =>
                            `${r.evaluation?.trajectory.total_duration_ms.toFixed(0) ?? "--"} ms`,
                        },
                        {
                          label: "Subagent Handoffs Executed",
                          render: (r: RunRecord) =>
                            String(r.evaluation?.trajectory.handoffs_count ?? 0),
                        },
                      ].map((row) => (
                        <tr key={row.label} className={row.highlight ? "bg-indigo-950/20 font-bold" : ""}>
                          <td className="p-3.5 text-slate-300">{row.label}</td>
                          {abResult.runs.map((r) => (
                            <td key={r.id} className="p-3.5 border-l border-slate-800 font-mono">
                              {row.render(r)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {/* ==================== TAB 6: AI ARCHITECTURE ADVISOR (v2 DIFF) ==================== */}
        {activeTab === "advisor" && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-indigo-400" />
                  AI Architecture Advisor — Automated Bottleneck Diagnosis & Spec Evolution
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Analyzes execution telemetry, verifier failures, and subagent token distribution to propose an actionable v2 YAML blueprint diff.
                </p>
              </div>
              {activeRun && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleLoadAdvisor(true)}
                    disabled={isLoadingAdvisor}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs cursor-pointer"
                  >
                    <RefreshCw className="w-3.5 h-3.5" /> Re-Analyze Trace
                  </button>
                  <button
                    onClick={() => handleApplyAdvisorPatch(false)}
                    disabled={!advisorSuggestion}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs cursor-pointer"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Apply Patch to `{advisorSuggestion?.architecture_id}` (v
                    {advisorSuggestion?.proposed_version})
                  </button>
                  <button
                    onClick={() => handleApplyAdvisorPatch(true)}
                    disabled={!advisorSuggestion}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Save as New v2 Blueprint
                  </button>
                  <button
                    onClick={async () => {
                      if (!activeRun || !advisorSuggestion) return;
                      try {
                        const applied = await api.applyAdvisorSuggestion(activeRun.id);
                        const targetFolder = exportDir.trim() || activeRun.sandbox_path;
                        const exp = await api.exportBlueprint(
                          applied.metadata.id,
                          activeRun.harness,
                          targetFolder,
                          activeRun.task_id
                        );
                        setBlueprints(await api.listBlueprints());
                        await handleSelectBlueprint(applied.metadata.id);
                        notify(
                          `Applied v${applied.metadata.version} patch AND re-deployed ${exp.files_written.length} updated ${activeRun.harness} files to ${exp.target_directory}!`
                        );
                      } catch (err: unknown) {
                        notify(err instanceof Error ? err.message : "Failed to re-deploy patch", "err");
                      }
                    }}
                    disabled={!advisorSuggestion}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs cursor-pointer"
                  >
                    <FolderOutput className="w-3.5 h-3.5" />
                    Apply Patch & Re-Deploy to Project
                  </button>
                </div>
              )}
            </div>

            {advisorSuggestion ? (
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-2">
                    <div className="text-xs font-bold uppercase text-indigo-400">
                      Executive Diagnosis Summary
                    </div>
                    <p className="text-sm text-white font-medium">{advisorSuggestion.summary}</p>
                    <div className="space-y-1 pt-2">
                      {advisorSuggestion.changes_made.map((c, i) => (
                        <div key={i} className="text-xs text-emerald-300 flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                          {c}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                      Trace Findings & Architectural Recommendations
                    </div>
                    {advisorSuggestion.diagnoses.map((d, idx) => (
                      <div
                        key={idx}
                        className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-1.5 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-cyan-300 font-semibold">
                            {d.target_component}
                          </span>
                          <span
                            className={`uppercase text-[10px] font-bold px-2 py-0.5 rounded ${d.severity === "critical"
                              ? "bg-rose-950 text-rose-300 border border-rose-700/50"
                              : d.severity === "warning"
                                ? "bg-amber-950 text-amber-300 border border-amber-700/50"
                                : "bg-indigo-950 text-indigo-300 border border-indigo-700/50"
                              }`}
                          >
                            {d.severity}
                          </span>
                        </div>
                        <div className="text-slate-200 font-medium">{d.finding}</div>
                        <div className="text-slate-400">
                          <strong className="text-emerald-400">Recommendation:</strong> {d.recommendation}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Unified YAML Spec Diff Viewer */}
                <div className="flex flex-col rounded-2xl bg-slate-900 border border-slate-800 overflow-hidden">
                  <div className="p-3.5 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between text-xs">
                    <span className="font-bold text-white">
                      Proposed Blueprint Diff (v{advisorSuggestion.base_version} → v
                      {advisorSuggestion.proposed_version})
                    </span>
                    <span className="font-mono text-[11px] text-slate-400">Unified YAML Patch</span>
                  </div>
                  <pre className="p-4 font-mono text-xs overflow-auto flex-1 leading-relaxed bg-slate-950">
                    {advisorSuggestion.unified_yaml_diff.split("\n").map((line, i) => (
                      <div
                        key={i}
                        className={
                          line.startsWith("+") && !line.startsWith("+++")
                            ? "text-emerald-400 bg-emerald-950/30 px-1"
                            : line.startsWith("-") && !line.startsWith("---")
                              ? "text-rose-400 bg-rose-950/30 px-1"
                              : line.startsWith("@@")
                                ? "text-cyan-400 font-bold mt-1"
                                : "text-slate-400"
                        }
                      >
                        {line}
                      </div>
                    ))}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="text-center py-20 text-slate-400">
                {isLoadingAdvisor
                  ? "Analyzing execution trace and synthesizing v2 architecture blueprint..."
                  : "Select an evaluated run and click 'Diagnose with AI Architecture Advisor'."}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
