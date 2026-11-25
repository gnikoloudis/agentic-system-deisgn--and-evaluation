"""Declarative Agent Architecture Blueprint schemas (YAML <-> React Flow)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


HarnessType = Literal["claude_code", "antigravity", "opencode"]


class BlueprintMetadata(BaseModel):
    id: str = Field(..., description="Unique slug identifier for the architecture blueprint")
    name: str = Field(..., description="Human-readable architecture title")
    version: str = Field(default="1.0.0", description="Semantic version string")
    description: str = Field(default="", description="Summary of the architecture topology and goal")
    tags: List[str] = Field(default_factory=list)
    author: str = Field(default="HarnessForge User")


class AgentPermissions(BaseModel):
    allow_shell: bool = Field(default=True, description="Whether shell/bash execution is allowed")
    allow_write: bool = Field(default=True, description="Whether file creation/editing is allowed")
    allow_network: bool = Field(default=False, description="Whether external web/network requests are allowed")
    allowed_commands: List[str] = Field(
        default_factory=list,
        description="Optional whitelist of shell command prefixes (empty means all when allow_shell=True)",
    )
    blocked_commands: List[str] = Field(
        default_factory=lambda: ["rm -rf /", "git push --force"],
        description="Explicitly forbidden shell command substrings",
    )


class ExecutionBudgets(BaseModel):
    max_turns: int = Field(default=40, ge=1, le=500)
    max_cost_usd: float = Field(default=2.50, ge=0.01)
    timeout_seconds: int = Field(default=600, ge=10)
    context_compaction_threshold_pct: int = Field(default=80, ge=20, le=99)


class OrchestratorSpec(BaseModel):
    id: str = Field(default="root_orchestrator")
    name: str = Field(default="Lead Orchestrator")
    role: str = Field(default="Root coordinator and task router")
    model: str = Field(
        default="default",
        description="Model tier ('default', 'reasoning', 'coding', 'fast') or explicit model ID",
    )
    harness_models: Dict[str, str] = Field(
        default_factory=dict,
        description="Optional explicit model ID per harness ('claude_code', 'antigravity', 'opencode') for the root orchestrator",
    )
    system_prompt: str = Field(
        default="You are the Lead Orchestrator. Coordinate subagents according to the workflow topology.",
    )
    tools: List[str] = Field(
        default_factory=lambda: ["read", "grep", "glob", "bash", "subagent"],
    )
    mcp_servers: List[str] = Field(
        default_factory=list,
        description="Assigned MCP server IDs this orchestrator is authorized to use",
    )
    permissions: AgentPermissions = Field(default_factory=AgentPermissions)
    budgets: ExecutionBudgets = Field(default_factory=ExecutionBudgets)


class SubagentSpec(BaseModel):
    id: str = Field(..., description="Subagent identifier (used in filename & invocation)")
    name: str = Field(..., description="Display name of the subagent")
    role: str = Field(..., description="Short role description used by orchestrator to route tasks")
    model: str = Field(
        default="coding",
        description="Model tier ('default', 'reasoning', 'coding', 'fast') or explicit model ID",
    )
    harness_models: Dict[str, str] = Field(
        default_factory=dict,
        description="Optional explicit model ID per harness ('claude_code', 'antigravity', 'opencode') for this subagent",
    )
    system_prompt: str = Field(..., description="Detailed system instructions for this subagent")
    tools: List[str] = Field(
        default_factory=lambda: ["read", "write", "edit", "grep", "glob", "bash"],
    )
    mcp_servers: List[str] = Field(
        default_factory=list,
        description="Assigned MCP server IDs this subagent is authorized to use",
    )
    permissions: AgentPermissions = Field(default_factory=AgentPermissions)
    max_turns: int = Field(default=20, ge=1, le=200)


class SkillSpec(BaseModel):
    id: str = Field(..., description="Skill or slash command slug")
    name: str = Field(..., description="Human-readable skill name")
    description: str = Field(..., description="When the agent should invoke or apply this skill")
    instructions: str = Field(default="", description="Markdown body of the skill / command (auto-loaded from SKILL.md if source_dir is set)")
    source_dir: Optional[str] = Field(
        default=None,
        description="Optional path to a local skill folder containing SKILL.md plus references/, scripts/, resources/, and assets/",
    )
    trigger_command: Optional[str] = Field(
        default=None,
        description="Optional slash command trigger (e.g. '/tdd-check')",
    )


class CommandSpec(BaseModel):
    id: str = Field(..., description="Slash command slug without leading slash (e.g. 'build-ui-epic')")
    description: str = Field(..., description="Short description displayed in the command list")
    prompt: str = Field(..., description="Prompt or instructions executed when the user invokes /<id>")
    agent: Optional[str] = Field(
        default=None,
        description="Optional target agent ID (e.g. 'root_orchestrator' or a subagent ID)",
    )


class HookSpec(BaseModel):
    id: str = Field(..., description="Unique hook rule ID")
    event: Literal["PreToolUse", "PostToolUse", "SubagentStop", "Stop", "UserPromptSubmit"] = Field(
        default="PreToolUse"
    )
    matcher: str = Field(
        default=".*",
        description="Regex matching tool names (e.g. 'Write|Edit|Bash')",
    )
    target_agent: str = Field(
        default="*",
        description="Agent ID this hook applies to ('*' for all, 'root_orchestrator', or subagent ID)",
    )
    action: Literal["allow", "block", "run_command", "warn"] = Field(default="block")
    command: Optional[str] = Field(
        default=None,
        description="Optional shell command to run when action == 'run_command'",
    )
    message: str = Field(
        default="Action blocked by architecture guardrail hook.",
        description="Message returned to the agent when blocked or warned",
    )


class MCPServerSpec(BaseModel):
    id: str = Field(..., description="MCP server name")
    description: str = Field(default="", description="What tools or external systems this MCP server exposes")
    transport: Literal["stdio", "sse", "http"] = Field(default="stdio")
    command: Optional[str] = Field(default=None, description="Executable for stdio MCP server")
    args: List[str] = Field(default_factory=list)
    url: Optional[str] = Field(default=None, description="Endpoint URL for sse/http MCP server")
    env: Dict[str, str] = Field(default_factory=dict)


class TopologyEdge(BaseModel):
    id: str = Field(..., description="Unique edge ID")
    source: str = Field(..., description="Source node ID (orchestrator, subagent, skill)")
    target: str = Field(..., description="Target node ID (subagent, skill, hook, mcp)")
    condition: str = Field(
        default="Always",
        description="Routing condition or handoff trigger description",
    )
    order: int = Field(default=1, ge=1, description="Execution sequence step number")
    required: bool = Field(
        default=True,
        description="Whether this transition must occur before task completion",
    )
    max_loops: int = Field(
        default=1,
        ge=1,
        le=20,
        description="Max allowed cyclic transitions along this edge (for Critic->Coder retry loops)",
    )


class TopologySpec(BaseModel):
    pattern: Literal[
        "solo",
        "sequential-pipeline",
        "generator-verifier-loop",
        "parallel-swarm",
        "router-dispatcher",
        "hierarchical-custom",
    ] = Field(default="generator-verifier-loop")
    enforcement_mode: Literal["prompt", "hook", "dual"] = Field(
        default="dual",
        description="Whether topology is enforced via system prompts, runtime state-machine hooks, or both",
    )
    entry_node: str = Field(default="root_orchestrator")
    edges: List[TopologyEdge] = Field(default_factory=list)


class NodePosition(BaseModel):
    x: float = 0.0
    y: float = 0.0


class VisualLayout(BaseModel):
    nodes: Dict[str, NodePosition] = Field(default_factory=dict)


class AgentArchitecture(BaseModel):
    """Root declarative specification for an Agentic Architecture Blueprint."""

    api_version: str = Field(default="harnessforge/v1")
    kind: Literal["AgentArchitecture"] = Field(default="AgentArchitecture")
    metadata: BlueprintMetadata
    orchestrator: OrchestratorSpec = Field(default_factory=OrchestratorSpec)
    subagents: List[SubagentSpec] = Field(default_factory=list)
    skills: List[SkillSpec] = Field(default_factory=list)
    commands: List[CommandSpec] = Field(default_factory=list)
    hooks: List[HookSpec] = Field(default_factory=list)
    mcp_servers: List[MCPServerSpec] = Field(default_factory=list)
    topology: TopologySpec = Field(default_factory=TopologySpec)
    visual_layout: VisualLayout = Field(default_factory=VisualLayout)

    @model_validator(mode="after")
    def normalize_topology_edges(self) -> "AgentArchitecture":
        """Canonicalize topology edges: separate agent-to-agent handoffs from skill bindings,
        auto-flip reversed skill->agent edges, prune dangling/duplicate edges, and renumber handoff steps 1..N."""
        agent_ids = {self.orchestrator.id} | {sa.id for sa in self.subagents}
        skill_ids = {sk.id for sk in self.skills}
        generic_handoff_re = re.compile(r"^step\s+\d+\s+handoff$", re.IGNORECASE)

        workflow_items: List[tuple[int, int, TopologyEdge]] = []
        skill_items: List[tuple[int, int, TopologyEdge]] = []
        seen_workflow_pairs: set[tuple[str, str]] = set()
        seen_skill_pairs: set[tuple[str, str]] = set()

        for idx, edge in enumerate(self.topology.edges):
            src, tgt = edge.source, edge.target

            # 1. Agent -> Agent workflow handoff edge
            if src in agent_ids and tgt in agent_ids and src != tgt:
                pair = (src, tgt)
                if pair in seen_workflow_pairs:
                    continue
                seen_workflow_pairs.add(pair)
                workflow_items.append((edge.order, idx, edge))
                continue

            # 2. Agent -> Skill binding edge
            if src in agent_ids and tgt in skill_ids:
                pair = (src, tgt)
                if pair in seen_skill_pairs:
                    continue
                seen_skill_pairs.add(pair)
                cond = (edge.condition or "").strip()
                if not cond or generic_handoff_re.match(cond):
                    cond = f"Applies /{tgt}"
                norm_edge = edge.model_copy(
                    update={"source": src, "target": tgt, "condition": cond, "required": False, "max_loops": 1}
                )
                skill_items.append((edge.order, idx, norm_edge))
                continue

            # 3. Reversed Skill -> Agent edge (auto-flip to Agent -> Skill)
            if src in skill_ids and tgt in agent_ids:
                agent_id, skill_id = tgt, src
                pair = (agent_id, skill_id)
                if pair in seen_skill_pairs:
                    continue
                seen_skill_pairs.add(pair)
                cond = (edge.condition or "").strip()
                if not cond or generic_handoff_re.match(cond):
                    cond = f"Applies /{skill_id}"
                norm_edge = edge.model_copy(
                    update={
                        "source": agent_id,
                        "target": skill_id,
                        "condition": cond,
                        "required": False,
                        "max_loops": 1,
                    }
                )
                skill_items.append((edge.order, idx, norm_edge))
                continue

            # Drop dangling or invalid edges (e.g., deleted node IDs or skill->skill)

        workflow_items.sort(key=lambda item: (item[0], item[1]))
        skill_items.sort(key=lambda item: (item[0], item[1]))

        normalized: List[TopologyEdge] = []
        for step_num, (_, _, ed) in enumerate(workflow_items, start=1):
            normalized.append(ed.model_copy(update={"order": step_num}))

        skill_base_order = len(normalized)
        for offset, (_, _, ed) in enumerate(skill_items, start=1):
            normalized.append(ed.model_copy(update={"order": skill_base_order + offset}))

        self.topology.edges = normalized
        return self

    def workflow_handoff_edges(self) -> List[TopologyEdge]:
        """Return strictly Agent-to-Agent workflow handoff edges sorted by execution order."""
        agent_ids = {self.orchestrator.id} | {sa.id for sa in self.subagents}
        return sorted(
            [e for e in self.topology.edges if e.source in agent_ids and e.target in agent_ids],
            key=lambda e: e.order,
        )

    def skill_binding_edges(self) -> List[TopologyEdge]:
        """Return strictly Agent-to-Skill assignment edges."""
        agent_ids = {self.orchestrator.id} | {sa.id for sa in self.subagents}
        skill_ids = {sk.id for sk in self.skills}
        return [e for e in self.topology.edges if e.source in agent_ids and e.target in skill_ids]

    def skills_for_agent(self, agent_id: str) -> List[SkillSpec]:
        """Return SkillSpec objects explicitly bound to `agent_id` via topology skill edges."""
        bound_ids = {e.target for e in self.skill_binding_edges() if e.source == agent_id}
        return [sk for sk in self.skills if sk.id in bound_ids]


class CompiledFile(BaseModel):
    """A single native harness configuration or hook script file generated by a HarnessAdapter."""

    relative_path: str
    content: str
    description: str
    executable: bool = False


class CompilationResult(BaseModel):
    """Complete compiled output for a target harness."""

    architecture_id: str
    architecture_version: str
    harness: HarnessType
    files: List[CompiledFile]
    cli_preview_command: str
    interactive_launch_command: str
    notes: List[str] = Field(default_factory=list)
