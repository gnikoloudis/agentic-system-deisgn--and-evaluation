"""Declarative Agent Architecture Blueprint schemas (YAML <-> React Flow)."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


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
    permissions: AgentPermissions = Field(default_factory=AgentPermissions)
    max_turns: int = Field(default=20, ge=1, le=200)


class SkillSpec(BaseModel):
    id: str = Field(..., description="Skill or slash command slug")
    name: str = Field(..., description="Human-readable skill name")
    description: str = Field(..., description="When the agent should invoke or apply this skill")
    instructions: str = Field(..., description="Markdown body of the skill / command")
    trigger_command: Optional[str] = Field(
        default=None,
        description="Optional slash command trigger (e.g. '/tdd-check')",
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
    hooks: List[HookSpec] = Field(default_factory=list)
    mcp_servers: List[MCPServerSpec] = Field(default_factory=list)
    topology: TopologySpec = Field(default_factory=TopologySpec)
    visual_layout: VisualLayout = Field(default_factory=VisualLayout)


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
