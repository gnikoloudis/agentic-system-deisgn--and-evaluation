import React, { useCallback, useEffect, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  type Node,
  type Edge,
  type Connection,
  Handle,
  Position,
} from "@xyflow/react";
import {
  Bot,
  Cpu,
  ShieldAlert,
  Sparkles,
  Wrench,
  Lock,
  Terminal,
} from "lucide-react";
import type { AgentArchitecture, HarnessModelsConfig, HarnessType } from "../types";

interface CustomNodeData extends Record<string, unknown> {
  label: string;
  nodeType: "orchestrator" | "subagent" | "skill" | "hook" | "mcp";
  subtitle: string;
  model?: string;
  resolvedModel?: string;
  allowWrite?: boolean;
  allowShell?: boolean;
  isActive?: boolean;
  isSelected?: boolean;
}

function ArchitectureNodeCard({ data }: { data: CustomNodeData }) {
  const badgeStyles: Record<CustomNodeData["nodeType"], string> = {
    orchestrator:
      "border-indigo-500/80 bg-gradient-to-br from-indigo-950/95 via-slate-900 to-slate-900 shadow-lg shadow-indigo-500/15",
    subagent:
      "border-cyan-500/70 bg-gradient-to-br from-cyan-950/90 via-slate-900 to-slate-900 shadow-lg shadow-cyan-500/10",
    skill:
      "border-emerald-500/70 bg-gradient-to-br from-emerald-950/85 via-slate-900 to-slate-900",
    hook:
      "border-amber-500/75 bg-gradient-to-br from-amber-950/85 via-slate-900 to-slate-900",
    mcp: "border-purple-500/70 bg-gradient-to-br from-purple-950/85 via-slate-900 to-slate-900",
  };

  const typeLabel: Record<CustomNodeData["nodeType"], string> = {
    orchestrator: "ROOT ORCHESTRATOR",
    subagent: "SUBAGENT",
    skill: "SKILL / COMMAND",
    hook: "GUARDRAIL HOOK",
    mcp: "MCP SERVER",
  };

  const IconComponent =
    data.nodeType === "orchestrator"
      ? Cpu
      : data.nodeType === "subagent"
      ? Bot
      : data.nodeType === "skill"
      ? Sparkles
      : data.nodeType === "hook"
      ? ShieldAlert
      : Wrench;

  return (
    <div
      className={`min-w-[235px] max-w-[270px] rounded-xl border-2 px-3.5 py-3 transition-all ${
        badgeStyles[data.nodeType]
      } ${
        data.isActive
          ? "ring-4 ring-emerald-400/80 scale-105 animate-pulse"
          : data.isSelected
          ? "ring-2 ring-white/90"
          : ""
      }`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!h-3 !w-3 !bg-indigo-400 !border-2 !border-slate-950"
      />
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="inline-flex items-center gap-1.5 text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded-full bg-slate-800/90 text-slate-200 border border-slate-700">
          <IconComponent className="w-3 h-3 text-indigo-400" />
          {typeLabel[data.nodeType]}
        </span>
      </div>

      {data.model && (
        <div className="mb-1.5 flex items-center gap-1 flex-wrap">
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-950/90 text-cyan-300 border border-cyan-800/60 truncate max-w-full">
            {data.resolvedModel && data.resolvedModel !== data.model
              ? `${data.model} → ${data.resolvedModel}`
              : data.resolvedModel || data.model}
          </span>
        </div>
      )}

      <div className="font-semibold text-sm text-white truncate">{data.label}</div>
      <div className="text-xs text-slate-300/90 line-clamp-2 mt-0.5 leading-relaxed">
        {data.subtitle}
      </div>

      {(data.nodeType === "orchestrator" || data.nodeType === "subagent") && (
        <div className="flex items-center gap-2 mt-2.5 pt-2 border-t border-slate-800/80 text-[10px] text-slate-300">
          <span
            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded ${
              data.allowWrite
                ? "bg-emerald-950/80 text-emerald-300 border border-emerald-700/50"
                : "bg-slate-800 text-slate-400"
            }`}
          >
            <Lock className="w-2.5 h-2.5" />
            {data.allowWrite ? "Write: ON" : "Read-Only"}
          </span>
          <span
            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded ${
              data.allowShell
                ? "bg-indigo-950/80 text-indigo-300 border border-indigo-700/50"
                : "bg-slate-800 text-slate-400"
            }`}
          >
            <Terminal className="w-2.5 h-2.5" />
            {data.allowShell ? "Shell: ON" : "No Shell"}
          </span>
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-3 !w-3 !bg-cyan-400 !border-2 !border-slate-950"
      />
    </div>
  );
}

const nodeTypes = {
  architectureNode: ArchitectureNodeCard,
};

interface Props {
  blueprint: AgentArchitecture;
  targetHarness: HarnessType;
  harnessModels?: HarnessModelsConfig | null;
  activeAgentId?: string | null;
  selectedNodeId: string | null;
  onSelectNode: (id: string) => void;
  onUpdateBlueprint: (updated: AgentArchitecture) => void;
}

export const ArchitectureCanvas: React.FC<Props> = ({
  blueprint,
  targetHarness,
  harnessModels,
  activeAgentId,
  selectedNodeId,
  onSelectNode,
  onUpdateBlueprint,
}) => {
  const resolveNodeModel = useCallback(
    (tierOrId: string, overrides?: Record<string, string>) => {
      if (overrides && overrides[targetHarness]?.trim()) {
        return overrides[targetHarness].trim();
      }
      const tierMap = harnessModels?.tier_map?.[targetHarness] || {};
      return tierMap[tierOrId] || tierOrId;
    },
    [targetHarness, harnessModels]
  );

  const initialNodesAndEdges = useMemo(() => {
    const layout = blueprint.visual_layout?.nodes || {};
    const flowNodes: Node[] = [];

    // 1. Root Orchestrator
    const orchPos = layout[blueprint.orchestrator.id] || { x: 380, y: 40 };
    flowNodes.push({
      id: blueprint.orchestrator.id,
      type: "architectureNode",
      position: orchPos,
      data: {
        label: blueprint.orchestrator.name,
        nodeType: "orchestrator",
        subtitle: blueprint.orchestrator.role,
        model: blueprint.orchestrator.model,
        resolvedModel: resolveNodeModel(
          blueprint.orchestrator.model,
          blueprint.orchestrator.harness_models
        ),
        allowWrite: blueprint.orchestrator.permissions.allow_write,
        allowShell: blueprint.orchestrator.permissions.allow_shell,
        isActive: activeAgentId === blueprint.orchestrator.id,
        isSelected: selectedNodeId === blueprint.orchestrator.id,
      },
    });

    // 2. Subagents
    blueprint.subagents.forEach((sa, idx) => {
      const pos = layout[sa.id] || { x: 100 + idx * 290, y: 230 };
      flowNodes.push({
        id: sa.id,
        type: "architectureNode",
        position: pos,
        data: {
          label: `${sa.name} (${sa.id})`,
          nodeType: "subagent",
          subtitle: sa.role,
          model: sa.model,
          resolvedModel: resolveNodeModel(sa.model, sa.harness_models),
          allowWrite: sa.permissions.allow_write,
          allowShell: sa.permissions.allow_shell,
          isActive: activeAgentId === sa.id,
          isSelected: selectedNodeId === sa.id,
        },
      });
    });

    // 3. Skills
    blueprint.skills.forEach((sk, idx) => {
      const pos = layout[sk.id] || { x: 140 + idx * 280, y: 430 };
      flowNodes.push({
        id: sk.id,
        type: "architectureNode",
        position: pos,
        data: {
          label: `${sk.name} (/${sk.id})`,
          nodeType: "skill",
          subtitle: sk.description,
          isActive: false,
          isSelected: selectedNodeId === sk.id,
        },
      });
    });

    // 4. Hooks
    blueprint.hooks.forEach((hk, idx) => {
      const pos = layout[hk.id] || { x: 680, y: 40 + idx * 140 };
      flowNodes.push({
        id: hk.id,
        type: "architectureNode",
        position: pos,
        data: {
          label: hk.id,
          nodeType: "hook",
          subtitle: `[${hk.event}] ${hk.matcher} -> ${hk.action.toUpperCase()}`,
          isActive: false,
          isSelected: selectedNodeId === hk.id,
        },
      });
    });

    // 5. MCP Servers
    (blueprint.mcp_servers || []).forEach((srv, idx) => {
      const pos = layout[srv.id] || { x: 680, y: 300 + idx * 130 };
      const endpointLabel =
        srv.transport === "stdio"
          ? `${srv.command || "npx"} ${(srv.args || []).slice(0, 2).join(" ")}`.trim()
          : srv.url || srv.transport;
      flowNodes.push({
        id: srv.id,
        type: "architectureNode",
        position: pos,
        data: {
          label: srv.id,
          nodeType: "mcp",
          subtitle: srv.description || `[${srv.transport.toUpperCase()}] ${endpointLabel}`,
          isActive: false,
          isSelected: selectedNodeId === srv.id,
        },
      });
    });

    const agentIds = new Set([
      blueprint.orchestrator.id,
      ...blueprint.subagents.map((s) => s.id),
    ]);
    const skillIds = new Set(blueprint.skills.map((s) => s.id));
    const hookIds = new Set(blueprint.hooks.map((h) => h.id));
    const mcpIds = new Set((blueprint.mcp_servers || []).map((m) => m.id));

    const workflowEdges = blueprint.topology.edges
      .filter((e) => agentIds.has(e.source) && agentIds.has(e.target))
      .sort((a, b) => a.order - b.order);

    const skillBindingEdges = blueprint.topology.edges.filter(
      (e) =>
        (agentIds.has(e.source) && skillIds.has(e.target)) ||
        (skillIds.has(e.source) && agentIds.has(e.target))
    );

    const flowEdges: Edge[] = [
      ...workflowEdges.map((e, idx) => {
        const stepNum = idx + 1;
        const isLoop = e.max_loops > 1 && !e.required;
        const strokeColor = isLoop
          ? "#f59e0b"
          : e.required
          ? "#38bdf8"
          : "#94a3b8";
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          label: `#${stepNum} ${e.condition}${e.max_loops > 1 ? ` (≤${e.max_loops}x)` : ""}`,
          animated: true,
          style: {
            stroke: strokeColor,
            strokeWidth: 2.2,
          },
          labelStyle: { fill: "#e2e8f0", fontSize: 11, fontWeight: 600 },
          labelBgStyle: { fill: "#0f172a", fillOpacity: 0.9 },
          labelBgPadding: [6, 3] as [number, number],
          labelBgBorderRadius: 6,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: strokeColor,
          },
        };
      }),
      ...skillBindingEdges.map((e) => {
        const isReversed = skillIds.has(e.source) && agentIds.has(e.target);
        const agentId = isReversed ? e.target : e.source;
        const skillId = isReversed ? e.source : e.target;
        return {
          id: e.id,
          source: agentId,
          target: skillId,
          label: `Uses Skill: /${skillId}`,
          animated: false,
          style: {
            stroke: "#10b981",
            strokeWidth: 2.0,
            strokeDasharray: "6 4",
          },
          labelStyle: { fill: "#a7f3d0", fontSize: 10, fontWeight: 600 },
          labelBgStyle: { fill: "#0f172a", fillOpacity: 0.9 },
          labelBgPadding: [6, 3] as [number, number],
          labelBgBorderRadius: 6,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: "#10b981",
          },
        };
      }),
    ];

    // Automatically render Guardrail Hook -> Target Agent binding edges
    blueprint.hooks.forEach((hk) => {
      const targetNodeId =
        hk.target_agent && hk.target_agent !== "*"
          ? hk.target_agent
          : blueprint.orchestrator.id;
      const alreadyHasEdge = flowEdges.some(
        (fe) =>
          (fe.source === hk.id && fe.target === targetNodeId) ||
          (fe.source === targetNodeId && fe.target === hk.id)
      );
      if (!alreadyHasEdge && hookIds.has(hk.id)) {
        flowEdges.push({
          id: `hook_bind_${hk.id}_${targetNodeId}`,
          source: hk.id,
          target: targetNodeId,
          label: `Guards [${hk.event}] (${hk.target_agent === "*" ? "All Agents" : hk.target_agent})`,
          animated: false,
          style: {
            stroke: "#f59e0b",
            strokeWidth: 2,
            strokeDasharray: "4 4",
          },
          labelStyle: { fill: "#fcd34d", fontSize: 10, fontWeight: 600 },
          labelBgStyle: { fill: "#0f172a", fillOpacity: 0.9 },
          labelBgPadding: [5, 2] as [number, number],
          labelBgBorderRadius: 5,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: "#f59e0b",
          },
        });
      }
    });

    // Automatically render Agent / Subagent -> Assigned MCP Server binding edges
    const addMcpEdge = (agentId: string, mcpId: string) => {
      if (!mcpIds.has(mcpId)) return;
      const alreadyHas = flowEdges.some(
        (fe) =>
          (fe.source === agentId && fe.target === mcpId) ||
          (fe.source === mcpId && fe.target === agentId)
      );
      if (!alreadyHas) {
        flowEdges.push({
          id: `mcp_bind_${agentId}_${mcpId}`,
          source: agentId,
          target: mcpId,
          label: `MCP: ${mcpId}`,
          animated: false,
          style: {
            stroke: "#a855f7",
            strokeWidth: 2,
            strokeDasharray: "5 4",
          },
          labelStyle: { fill: "#d8b4fe", fontSize: 10, fontWeight: 600 },
          labelBgStyle: { fill: "#0f172a", fillOpacity: 0.9 },
          labelBgPadding: [5, 2] as [number, number],
          labelBgBorderRadius: 5,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: "#a855f7",
          },
        });
      }
    };
    (blueprint.orchestrator.mcp_servers || []).forEach((mid) =>
      addMcpEdge(blueprint.orchestrator.id, mid)
    );
    blueprint.subagents.forEach((sa) => {
      (sa.mcp_servers || []).forEach((mid) => addMcpEdge(sa.id, mid));
    });

    return { flowNodes, flowEdges };
  }, [blueprint, activeAgentId, selectedNodeId, resolveNodeModel]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodesAndEdges.flowNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialNodesAndEdges.flowEdges);

  useEffect(() => {
    setNodes(initialNodesAndEdges.flowNodes);
    setEdges(initialNodesAndEdges.flowEdges);
  }, [initialNodesAndEdges, setNodes, setEdges]);

  const onNodeDragStop = useCallback(
    (_: unknown, draggedNode: Node) => {
      const nextLayout = {
        ...(blueprint.visual_layout?.nodes || {}),
        [draggedNode.id]: {
          x: Math.round(draggedNode.position.x),
          y: Math.round(draggedNode.position.y),
        },
      };
      onUpdateBlueprint({
        ...blueprint,
        visual_layout: { nodes: nextLayout },
      });
    },
    [blueprint, onUpdateBlueprint]
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      // If dragging from a Guardrail Hook node to an Agent node, bind hook.target_agent to that agent
      const sourceHook = blueprint.hooks.find((h) => h.id === connection.source);
      if (sourceHook) {
        const updatedHooks = blueprint.hooks.map((h) =>
          h.id === sourceHook.id ? { ...h, target_agent: connection.target! } : h
        );
        onUpdateBlueprint({
          ...blueprint,
          hooks: updatedHooks,
        });
        return;
      }

      // If dragging between an Agent/Subagent and an MCP Server node, assign that MCP server to the agent
      const allMcps = blueprint.mcp_servers || [];
      const mcpFromTarget = allMcps.find((m) => m.id === connection.target);
      const mcpFromSource = allMcps.find((m) => m.id === connection.source);
      if (mcpFromTarget || mcpFromSource) {
        const mcpId = (mcpFromTarget || mcpFromSource)!.id;
        const agentId = mcpFromTarget ? connection.source : connection.target;
        if (agentId === blueprint.orchestrator.id) {
          const curr = blueprint.orchestrator.mcp_servers || [];
          if (!curr.includes(mcpId)) {
            onUpdateBlueprint({
              ...blueprint,
              orchestrator: { ...blueprint.orchestrator, mcp_servers: [...curr, mcpId] },
            });
          }
          return;
        }
        const targetSa = blueprint.subagents.find((s) => s.id === agentId);
        if (targetSa) {
          const curr = targetSa.mcp_servers || [];
          if (!curr.includes(mcpId)) {
            onUpdateBlueprint({
              ...blueprint,
              subagents: blueprint.subagents.map((s) =>
                s.id === targetSa.id ? { ...s, mcp_servers: [...curr, mcpId] } : s
              ),
            });
          }
          return;
        }
      }

      const agentIds = new Set([
        blueprint.orchestrator.id,
        ...blueprint.subagents.map((s) => s.id),
      ]);
      const skillIds = new Set(blueprint.skills.map((s) => s.id));

      const isSourceSkill = skillIds.has(connection.source);
      const isTargetSkill = skillIds.has(connection.target);

      // Skill <-> Agent binding (always normalize direction to Agent -> Skill, required: false)
      if (isSourceSkill || isTargetSkill) {
        if (isSourceSkill && isTargetSkill) return; // Cannot connect skill to skill
        const agentId = isSourceSkill ? connection.target : connection.source;
        const skillId = isSourceSkill ? connection.source : connection.target;
        if (!agentIds.has(agentId)) return;

        const alreadyBound = blueprint.topology.edges.some(
          (e) =>
            (e.source === agentId && e.target === skillId) ||
            (e.source === skillId && e.target === agentId)
        );
        if (alreadyBound) return;

        const existingWorkflow = blueprint.topology.edges
          .filter((e) => agentIds.has(e.source) && agentIds.has(e.target))
          .sort((a, b) => a.order - b.order)
          .map((e, i) => ({ ...e, order: i + 1 }));
        const existingSkills = blueprint.topology.edges
          .filter(
            (e) =>
              (agentIds.has(e.source) && skillIds.has(e.target)) ||
              (skillIds.has(e.source) && agentIds.has(e.target))
          )
          .map((e) =>
            skillIds.has(e.source)
              ? { ...e, source: e.target, target: e.source, required: false, max_loops: 1 }
              : { ...e, required: false, max_loops: 1 }
          );

        const newSkillEdge = {
          id: `e_${agentId}_${skillId}_${Date.now().toString().slice(-3)}`,
          source: agentId,
          target: skillId,
          condition: `Applies /${skillId}`,
          order: existingWorkflow.length + existingSkills.length + 1,
          required: false,
          max_loops: 1,
        };
        const reorderedSkills = [...existingSkills, newSkillEdge]
          .sort((a, b) => a.source.localeCompare(b.source) || a.target.localeCompare(b.target))
          .map((e, i) => ({
            ...e,
            order: existingWorkflow.length + i + 1,
          }));
        onUpdateBlueprint({
          ...blueprint,
          topology: {
            ...blueprint.topology,
            edges: [...existingWorkflow, ...reorderedSkills],
          },
        });
        return;
      }

      // Agent -> Agent workflow handoff edge
      if (!agentIds.has(connection.source) || !agentIds.has(connection.target)) return;
      if (connection.source === connection.target) return;
      const alreadyExists = blueprint.topology.edges.some(
        (e) => e.source === connection.source && e.target === connection.target
      );
      if (alreadyExists) return;

      const existingWorkflow = blueprint.topology.edges
        .filter((e) => agentIds.has(e.source) && agentIds.has(e.target))
        .sort((a, b) => a.order - b.order);
      const existingSkills = blueprint.topology.edges.filter(
        (e) =>
          (agentIds.has(e.source) && skillIds.has(e.target)) ||
          (skillIds.has(e.source) && agentIds.has(e.target))
      );

      const nextOrder = existingWorkflow.length + 1;
      const newEdgeId = `e_${connection.source}_${connection.target}_${Date.now().toString().slice(-3)}`;
      const nextWorkflow = [
        ...existingWorkflow,
        {
          id: newEdgeId,
          source: connection.source,
          target: connection.target,
          condition: `Step ${nextOrder}: Delegate to ${connection.target}`,
          order: nextOrder,
          required: true,
          max_loops: 1,
        },
      ].map((e, i) => ({ ...e, order: i + 1 }));
      const nextSkills = existingSkills.map((e, i) => ({
        ...e,
        order: nextWorkflow.length + i + 1,
      }));

      onUpdateBlueprint({
        ...blueprint,
        topology: {
          ...blueprint.topology,
          edges: [...nextWorkflow, ...nextSkills],
        },
      });
    },
    [blueprint, onUpdateBlueprint]
  );

  const onNodesDelete = useCallback(
    (deletedNodes: Node[]) => {
      const deletedIds = new Set(
        deletedNodes
          .map((n) => n.id)
          .filter((id) => id !== blueprint.orchestrator.id)
      );
      if (deletedIds.size === 0) return;

      const nextLayoutNodes = { ...(blueprint.visual_layout?.nodes || {}) };
      deletedIds.forEach((id) => {
        delete nextLayoutNodes[id];
      });

      onUpdateBlueprint({
        ...blueprint,
        orchestrator: {
          ...blueprint.orchestrator,
          mcp_servers: (blueprint.orchestrator.mcp_servers || []).filter((m) => !deletedIds.has(m)),
        },
        subagents: blueprint.subagents
          .filter((s) => !deletedIds.has(s.id))
          .map((s) => ({
            ...s,
            mcp_servers: (s.mcp_servers || []).filter((m) => !deletedIds.has(m)),
          })),
        skills: blueprint.skills.filter((sk) => !deletedIds.has(sk.id)),
        hooks: blueprint.hooks.filter((h) => !deletedIds.has(h.id)),
        mcp_servers: (blueprint.mcp_servers || []).filter((m) => !deletedIds.has(m.id)),
        topology: {
          ...blueprint.topology,
          edges: blueprint.topology.edges.filter(
            (e) => !deletedIds.has(e.source) && !deletedIds.has(e.target)
          ),
        },
        visual_layout: { nodes: nextLayoutNodes },
      });
      onSelectNode(blueprint.orchestrator.id);
    },
    [blueprint, onUpdateBlueprint, onSelectNode]
  );

  const onEdgesDelete = useCallback(
    (deletedEdges: Edge[]) => {
      const deletedEdgeIds = new Set(deletedEdges.map((e) => e.id));
      const remainingEdges = blueprint.topology.edges.filter((e) => !deletedEdgeIds.has(e.id));
      if (remainingEdges.length === blueprint.topology.edges.length) return;

      const agentIds = new Set([
        blueprint.orchestrator.id,
        ...blueprint.subagents.map((s) => s.id),
      ]);
      const skillIds = new Set(blueprint.skills.map((s) => s.id));
      const workflowEdges = remainingEdges
        .filter((e) => agentIds.has(e.source) && agentIds.has(e.target))
        .sort((a, b) => a.order - b.order)
        .map((e, i) => ({ ...e, order: i + 1 }));
      const skillEdges = remainingEdges
        .filter(
          (e) =>
            (agentIds.has(e.source) && skillIds.has(e.target)) ||
            (skillIds.has(e.source) && agentIds.has(e.target))
        )
        .map((e) =>
          skillIds.has(e.source)
            ? { ...e, source: e.target, target: e.source, required: false, max_loops: 1 }
            : e
        )
        .sort((a, b) => a.source.localeCompare(b.source) || a.target.localeCompare(b.target))
        .map((e, i) => ({ ...e, order: workflowEdges.length + i + 1 }));

      onUpdateBlueprint({
        ...blueprint,
        topology: {
          ...blueprint.topology,
          edges: [...workflowEdges, ...skillEdges],
        },
      });
    },
    [blueprint, onUpdateBlueprint]
  );

  return (
    <div className="w-full h-full bg-slate-950 relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodesDelete={onNodesDelete}
        onEdgesDelete={onEdgesDelete}
        onNodeDragStop={onNodeDragStop}
        onConnect={onConnect}
        onNodeClick={(_, node) => onSelectNode(node.id)}
        fitView
        fitViewOptions={{ padding: 0.22 }}
      >
        <Background color="#1e293b" gap={22} size={1.5} />
        <Controls className="!bg-slate-900 !border-slate-700 !rounded-lg" />
        <MiniMap
          nodeColor={(n) =>
            n.data?.nodeType === "orchestrator"
              ? "#6366f1"
              : n.data?.nodeType === "subagent"
              ? "#06b6d4"
              : "#10b981"
          }
          maskColor="rgba(2, 6, 23, 0.75)"
          className="!bg-slate-900 !border !border-slate-800 !rounded-lg"
        />
      </ReactFlow>
    </div>
  );
};
