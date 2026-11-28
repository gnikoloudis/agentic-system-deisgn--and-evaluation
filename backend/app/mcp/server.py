"""HarnessForge FastMCP Server.

Exposes HarnessForge agent architecture design, compilation, deployment,
benchmark task authoring, evaluation, and AI Advisor capabilities via the Model Context Protocol (MCP).
Supports dual mode: direct Python engine (default) or HTTP proxy via HARNESSFORGE_API_URL.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from mcp.server.fastmcp import FastMCP

from app.compilers import compile_architecture, deploy_compiled_files
from app.config import BLUEPRINTS_DIR, ROOT_DIR, TASKS_DIR, ensure_directories, settings
from app.db.database import get_run, init_db
from app.db.storage import (
    blueprint_to_yaml,
    get_blueprint,
    get_task,
    list_blueprints,
    list_tasks,
    save_blueprint,
    save_task,
    yaml_to_blueprint,
    yaml_to_task,
)
from app.evaluator.advisor import generate_advisor_suggestion
from app.mcp.catalog import (
    get_all_available_mcp_servers,
    get_mcp_presets,
    resolve_mcp_spec,
)
from app.runner.executor import start_execution_run
from app.schemas.blueprint import (
    AgentArchitecture,
    BlueprintMetadata,
    HarnessType,
    MCPServerSpec,
    OrchestratorSpec,
    SubagentSpec,
    TopologyEdge,
    TopologySpec,
)
from app.schemas.evaluation import RunMode
from app.schemas.task import RubricDimension, TaskSpec, VerificationCheck

# Initialize FastMCP Server
mcp_server = FastMCP(
    "harnessforge",
    instructions=(
        "HarnessForge MCP Server: Design, compile, deploy, benchmark, and evaluate multi-agent architectures "
        "for Claude Code, Antigravity, and OpenCode with native MCP integration."
    ),
)


# Helper: Initialize DB and directories lazily
def _ensure_backend_ready() -> None:
    ensure_directories()
    init_db()


@mcp_server.tool()
def list_mcp_catalog(workspace_dir: str = "") -> str:
    """List all available MCP server presets and host-detected MCP servers.

    Args:
        workspace_dir: Optional workspace directory to scan for local mcp.json files.

    Returns:
        JSON string containing the list of available MCP servers with their IDs, descriptions, and commands.
    """
    _ensure_backend_ready()
    target_path = Path(workspace_dir) if workspace_dir else ROOT_DIR
    servers = get_all_available_mcp_servers(target_path)
    output = [
        {
            "id": s.id,
            "description": s.description,
            "transport": s.transport,
            "command": s.command,
            "args": s.args,
            "env": {k: "***" if "token" in k.lower() or "key" in k.lower() else v for k, v in s.env.items()},
        }
        for s in servers
    ]
    return json.dumps({"count": len(output), "mcp_servers": output}, indent=2)


@mcp_server.tool()
def list_blueprints_and_tasks() -> str:
    """List all architecture blueprints and benchmark tasks available in HarnessForge.

    Returns:
        JSON string summarizing all existing blueprints and benchmark tasks.
    """
    _ensure_backend_ready()
    bps = list_blueprints()
    tasks = list_tasks()
    return json.dumps(
        {
            "blueprints": [
                {
                    "id": bp.metadata.id,
                    "name": bp.metadata.name,
                    "version": bp.metadata.version,
                    "description": bp.metadata.description,
                    "orchestrator": bp.orchestrator.id,
                    "subagents": [sa.id for sa in bp.subagents],
                    "mcp_servers": [srv.id for srv in bp.mcp_servers],
                }
                for bp in bps
            ],
            "benchmark_tasks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "verifiers_count": len(t.verifiers),
                }
                for t in tasks
            ],
        },
        indent=2,
    )


@mcp_server.tool()
def inspect_blueprint(blueprint_id: str) -> str:
    """Get full details and raw YAML of a specific architecture blueprint.

    Args:
        blueprint_id: Blueprint ID (e.g. 'technical-business-analyst').

    Returns:
        Raw YAML representation and metadata of the blueprint.
    """
    _ensure_backend_ready()
    found = get_blueprint(blueprint_id)
    if not found:
        return json.dumps({"error": f"Blueprint `{blueprint_id}` not found."})
    bp, raw_yaml, path = found
    return json.dumps(
        {
            "id": bp.metadata.id,
            "name": bp.metadata.name,
            "file_path": str(path),
            "yaml": raw_yaml,
            "orchestrator": bp.orchestrator.id,
            "subagents": [sa.id for sa in bp.subagents],
            "mcp_servers": [srv.id for srv in bp.mcp_servers],
        },
        indent=2,
    )


@mcp_server.tool()
def describe_and_build_system(
    description: str,
    target_harness: str = "antigravity",
    topology_pattern: str = "generator-verifier-loop",
    mcp_servers: str = "",
    system_id: str = "",
    system_name: str = "",
) -> str:
    """Describe an agentic system in natural language and automatically build a valid HarnessForge architecture blueprint.

    Wires up requested MCP servers (e.g. 'sqlite, yahoofinance' or 'code-graph'), configures subagents,
    assigns permissions with least privilege, and constructs topology transitions.

    Args:
        description: Plain-English description of the multi-agent system, its purpose, roles, and workflow.
        target_harness: Primary target harness ('antigravity', 'claude_code', or 'opencode').
        topology_pattern: Workflow pattern ('generator-verifier-loop', 'sequential-pipeline', 'parallel-swarm', 'solo').
        mcp_servers: Comma-separated list of MCP server IDs needed by the system (e.g. 'code-graph, sqlite, yahoofinance').
        system_id: Optional slug ID for the architecture. If empty, derived from description/name.
        system_name: Optional human-readable name for the architecture.

    Returns:
        JSON string containing the created blueprint metadata, YAML definition, and assigned subagents.
    """
    _ensure_backend_ready()

    # Parse requested MCP IDs
    requested_mcps = [m.strip() for m in mcp_servers.split(",") if m.strip()]

    # Derive clean ID and Name
    clean_id = (
        re.sub(r"[^a-z0-9_-]+", "-", system_id.strip().lower()).strip("-")
        if system_id
        else re.sub(r"[^a-z0-9_-]+", "-", description.split(".")[0].strip().lower()[:32]).strip("-")
    )
    if not clean_id:
        clean_id = "agentic-system-custom"

    display_name = system_name.strip() if system_name else clean_id.replace("-", " ").title()

    # Resolve MCP specs from catalog
    resolved_mcps: List[MCPServerSpec] = [resolve_mcp_spec(m) for m in requested_mcps]

    # Model resolution based on harness
    default_orch_models = {
        "antigravity": "gemini-4-argon-medium",
        "claude_code": "claude-3-5-sonnet-20241022",
        "opencode": "deepseek-v4.1-flash-free",
    }
    default_subagent_models = {
        "antigravity": "gemini-4-argon-high",
        "claude_code": "claude-3-5-sonnet-20241022",
        "opencode": "big-pickle",
    }
    default_verifier_models = {
        "antigravity": "gemini-4-neon-high",
        "claude_code": "claude-3-5-sonnet-20241022",
        "opencode": "deepseek-v4.1-flash-free",
    }

    # Generate specialized subagents based on description and MCPs
    subagents: List[SubagentSpec] = []
    edges: List[TopologyEdge] = []

    # Domain heuristic to tailor roles
    is_financial = any(m in requested_mcps for m in ["sqlite", "yahoofinance"]) or "financial" in description.lower()
    is_tdd = "tdd" in description.lower() or "test-driven" in description.lower() or "user story" in description.lower()
    is_security = "security" in description.lower() or "bugfix" in description.lower() or "triage" in description.lower() or "code-graph" in requested_mcps

    if is_financial:
        subagents = [
            SubagentSpec(
                id="market_data_collector",
                name="Market Data & News Ingestion Analyst",
                role="Uses yahoofinance and sqlite MCPs to fetch ticker history, earnings reports, and historical news.",
                model="coding",
                harness_models={target_harness: default_subagent_models.get(target_harness, "default")},
                system_prompt="Fetch stock price history, company metrics, and recent news articles via Yahoo Finance and SQLite MCP tools. Never fabricate financial data.",
                tools=["read", "grep", "glob"],
                mcp_servers=[m for m in requested_mcps if m in ["sqlite", "yahoofinance"]],
                permissions={"allow_shell": False, "allow_write": True, "allow_network": True},
                max_turns=15,
            ),
            SubagentSpec(
                id="correlation_analyst",
                name="Financial Correlation & Anomaly Analyst",
                role="Correlates historical price movements with news sentiment and macro events, storing findings in SQLite.",
                model="reasoning",
                harness_models={target_harness: default_verifier_models.get(target_harness, "default")},
                system_prompt="Analyze ingested financial data for anomalies and correlations with published news. Formulate structured insight tables and charts.",
                tools=["read", "write", "edit", "grep"],
                mcp_servers=[m for m in requested_mcps if m in ["sqlite"]],
                permissions={"allow_shell": False, "allow_write": True, "allow_network": False},
                max_turns=20,
            ),
            SubagentSpec(
                id="report_qa_auditor",
                name="Financial Report QA & Verification Auditor",
                role="Verifies calculations, source citations, and outputs against deterministic accuracy checks.",
                model="reasoning",
                harness_models={target_harness: default_verifier_models.get(target_harness, "default")},
                system_prompt="Audit all generated financial findings. Verify numbers against SQLite queries and confirm zero hallucinated tickers.",
                tools=["read", "bash"],
                mcp_servers=[m for m in requested_mcps if m in ["sqlite"]],
                permissions={"allow_shell": True, "allow_write": False, "allow_network": False},
                max_turns=12,
            ),
        ]
    elif is_tdd:
        subagents = [
            SubagentSpec(
                id="test_suite_author",
                name="TDD Test Suite Author (Red Phase)",
                role="Reads user stories and acceptance criteria, then drafts comprehensive pytest suites before implementation begins.",
                model="coding",
                harness_models={target_harness: default_subagent_models.get(target_harness, "default")},
                system_prompt="Write comprehensive, failing unit and integration tests based on the user story acceptance criteria. Strictly follow TDD Red Phase.",
                tools=["read", "write", "edit", "grep", "glob"],
                mcp_servers=[m for m in requested_mcps if m != "stitch"],
                permissions={"allow_shell": False, "allow_write": True, "allow_network": False},
                max_turns=15,
            ),
            SubagentSpec(
                id="feature_developer",
                name="Feature Implementation Developer (Green Phase)",
                role="Implements minimal clean code to make all test cases pass without modifying the tests.",
                model="coding",
                harness_models={target_harness: default_subagent_models.get(target_harness, "default")},
                system_prompt="Implement the requested functions and classes to pass all authored tests. Do not touch test files.",
                tools=["read", "write", "edit", "grep", "glob"],
                mcp_servers=[m for m in requested_mcps if m != "stitch"],
                permissions={"allow_shell": False, "allow_write": True, "allow_network": False},
                max_turns=25,
            ),
            SubagentSpec(
                id="refactor_and_verifier",
                name="TDD Refactorer & Coverage Verifier (Refactor Phase)",
                role="Runs pytest suites, audits code coverage, refactors code for cleanliness, and validates final pass verdict.",
                model="reasoning",
                harness_models={target_harness: default_verifier_models.get(target_harness, "default")},
                system_prompt="Run pytest -v inside the sandbox, verify 100% test pass rate and high coverage, and refactor for maintainability.",
                tools=["read", "write", "edit", "bash"],
                mcp_servers=[m for m in requested_mcps],
                permissions={"allow_shell": True, "allow_write": True, "allow_network": False},
                max_turns=15,
            ),
        ]
    elif is_security:
        subagents = [
            SubagentSpec(
                id="code_graph_architect",
                name="Codebase AST & Impact Auditor",
                role="Uses code-graph MCP to inspect AST nodes, call graphs, and dead code to locate vulnerable entrypoints.",
                model="reasoning",
                harness_models={target_harness: default_verifier_models.get(target_harness, "default")},
                system_prompt="Inspect the codebase using code-graph MCP tools. Map function call trees, data flow, and identify vulnerability blast radius.",
                tools=["read", "grep", "glob"],
                mcp_servers=[m for m in requested_mcps if m == "code-graph"],
                permissions={"allow_shell": False, "allow_write": False, "allow_network": False},
                max_turns=15,
            ),
            SubagentSpec(
                id="security_patch_engineer",
                name="Security Patch & Bugfix Engineer",
                role="Applies targeted, least-intrusive patches to fix identified security vulnerabilities and bugs.",
                model="coding",
                harness_models={target_harness: default_subagent_models.get(target_harness, "default")},
                system_prompt="Implement precise security patches and bugfixes. Ensure no regressions in existing functionality.",
                tools=["read", "write", "edit", "grep", "glob"],
                mcp_servers=[m for m in requested_mcps if m == "code-graph"],
                permissions={"allow_shell": False, "allow_write": True, "allow_network": False},
                max_turns=20,
            ),
            SubagentSpec(
                id="regression_security_verifier",
                name="Regression & Static Audit Verifier",
                role="Executes pytest suites, AST validation, and security regression checks to ensure zero vulnerabilities remain.",
                model="reasoning",
                harness_models={target_harness: default_verifier_models.get(target_harness, "default")},
                system_prompt="Run pytest -v, execute AST static checks, and verify that the security issue is resolved with zero side effects.",
                tools=["read", "bash"],
                mcp_servers=[m for m in requested_mcps if m == "code-graph"],
                permissions={"allow_shell": True, "allow_write": False, "allow_network": False},
                max_turns=12,
            ),
        ]
    else:
        # General multi-agent builder
        subagents = [
            SubagentSpec(
                id="specialist_investigator",
                name="Domain Specialist & Investigator",
                role="Explores requirements, analyzes inputs, and utilizes assigned MCP servers.",
                model="coding",
                harness_models={target_harness: default_subagent_models.get(target_harness, "default")},
                system_prompt="Investigate inputs and utilize assigned MCP tools to formulate the core plan.",
                tools=["read", "grep", "glob"],
                mcp_servers=requested_mcps,
                permissions={"allow_shell": False, "allow_write": True, "allow_network": False},
                max_turns=15,
            ),
            SubagentSpec(
                id="implementation_specialist",
                name="Implementation Specialist",
                role="Executes the planned changes with write access.",
                model="coding",
                harness_models={target_harness: default_subagent_models.get(target_harness, "default")},
                system_prompt="Implement deliverables accurately according to the plan.",
                tools=["read", "write", "edit", "grep", "glob"],
                mcp_servers=requested_mcps,
                permissions={"allow_shell": False, "allow_write": True, "allow_network": False},
                max_turns=20,
            ),
            SubagentSpec(
                id="quality_verifier",
                name="Quality & Test Verifier",
                role="Validates outputs and runs verification checks.",
                model="reasoning",
                harness_models={target_harness: default_verifier_models.get(target_harness, "default")},
                system_prompt="Audit deliverables and execute verification tests to ensure quality.",
                tools=["read", "bash"],
                mcp_servers=requested_mcps,
                permissions={"allow_shell": True, "allow_write": False, "allow_network": False},
                max_turns=12,
            ),
        ]

    # Build orchestrator
    orchestrator = OrchestratorSpec(
        id=f"{clean_id.replace('-', '_')}_orchestrator",
        name=f"{display_name} Lead Orchestrator",
        role=f"Leads and coordinates the {display_name} pipeline across subagents.",
        model="default",
        harness_models={target_harness: default_orch_models.get(target_harness, "default")},
        system_prompt=(
            f"You are the Lead Orchestrator for {display_name}.\n"
            f"Description: {description}\n"
            f"Delegate in strict sequence to your specialist subagents:\n"
            + "\n".join(f"{i+1}. Delegate to `{sa.id}`: {sa.role}" for i, sa in enumerate(subagents))
            + "\nEnsure all deliverables pass verification checks before declaring completion."
        ),
        tools=["read", "grep", "glob", "subagent"],
        mcp_servers=requested_mcps[:1] if requested_mcps else [],
        permissions={"allow_shell": False, "allow_write": False, "allow_network": False},
        budgets={"max_turns": 40, "max_cost_usd": 3.0, "timeout_seconds": 600},
    )

    # Build topology edges
    edges.append(
        TopologyEdge(
            id=f"edge_orch_to_{subagents[0].id}",
            source=orchestrator.id,
            target=subagents[0].id,
            condition="Step 1: Ingest and analyze domain requirements",
            order=1,
            required=True,
            max_loops=1,
        )
    )
    for i in range(len(subagents) - 1):
        edges.append(
            TopologyEdge(
                id=f"edge_{subagents[i].id}_to_{subagents[i+1].id}",
                source=subagents[i].id,
                target=subagents[i+1].id,
                condition=f"Step {i+2}: Handoff to {subagents[i+1].name}",
                order=i + 2,
                required=True,
                max_loops=1,
            )
        )
    # Loop back edge if generator-verifier-loop
    if topology_pattern == "generator-verifier-loop" and len(subagents) >= 2:
        edges.append(
            TopologyEdge(
                id=f"edge_loopback_{subagents[-1].id}_to_{subagents[-2].id}",
                source=subagents[-1].id,
                target=subagents[-2].id,
                condition="Conditional: If verifier reports FAIL, loop back for revision (max 3 loops)",
                order=len(subagents) + 1,
                required=False,
                max_loops=3,
            )
        )

    # Construct AgentArchitecture
    valid_topology_patterns = [
        "solo",
        "sequential-pipeline",
        "generator-verifier-loop",
        "parallel-swarm",
        "router-dispatcher",
        "hierarchical-custom",
    ]
    pattern_val = topology_pattern if topology_pattern in valid_topology_patterns else "generator-verifier-loop"

    blueprint = AgentArchitecture(
        api_version="harnessforge/v1",
        kind="AgentArchitecture",
        metadata=BlueprintMetadata(
            id=clean_id,
            name=display_name,
            version="1.0.0",
            description=description,
            tags=[target_harness, "mcp", pattern_val],
        ),
        orchestrator=orchestrator,
        subagents=subagents,
        skills=[],
        commands=[],
        guardrail_hooks=[],
        mcp_servers=resolved_mcps,
        topology=TopologySpec(
            pattern=pattern_val,
            edges=edges,
            runtime_enforcement="dual",
        ),
    )

    blueprint.normalize_topology_edges()
    yaml_str = blueprint_to_yaml(blueprint)

    return json.dumps(
        {
            "status": "success",
            "blueprint_id": clean_id,
            "name": display_name,
            "orchestrator_id": orchestrator.id,
            "subagents": [sa.id for sa in subagents],
            "mcp_servers": [srv.id for srv in resolved_mcps],
            "yaml": yaml_str,
        },
        indent=2,
    )


@mcp_server.tool()
def validate_and_save_blueprint(blueprint_yaml: str) -> str:
    """Validate a blueprint YAML string against the HarnessForge schema and save it to disk.

    Args:
        blueprint_yaml: The raw YAML string of the AgentArchitecture blueprint.

    Returns:
        JSON string confirming validation, saved file path, and blueprint summary.
    """
    _ensure_backend_ready()
    try:
        bp = yaml_to_blueprint(blueprint_yaml)
    except Exception as exc:
        return json.dumps({"status": "error", "message": f"Schema validation failed: {exc}"})

    saved_bp, clean_yaml, target_path = save_blueprint(bp)
    return json.dumps(
        {
            "status": "success",
            "blueprint_id": saved_bp.metadata.id,
            "name": saved_bp.metadata.name,
            "file_path": str(target_path),
            "subagents_count": len(saved_bp.subagents),
            "mcp_servers": [srv.id for srv in saved_bp.mcp_servers],
        },
        indent=2,
    )


@mcp_server.tool()
def compile_and_deploy_system(
    blueprint_id: str,
    harness: str = "antigravity",
    target_workspace_dir: str = "",
    external_docs_dir: str = "",
) -> str:
    """Compile an agent architecture and deploy native files directly to a target workspace.

    Generates all native agent prompts, skills, commands, rules, telemetry hooks, and mcp.json
    for Claude Code, Antigravity, or OpenCode.

    Args:
        blueprint_id: Blueprint ID (e.g. 'mcp-antigravity-fullstack-studio').
        harness: Target harness ('antigravity', 'claude_code', or 'opencode').
        target_workspace_dir: Directory where the system should be deployed.
        external_docs_dir: Optional path to external reference documentation directory.

    Returns:
        JSON string listing all generated files, target harness, and deployment status.
    """
    _ensure_backend_ready()
    found = get_blueprint(blueprint_id)
    if not found:
        return json.dumps({"status": "error", "message": f"Blueprint `{blueprint_id}` not found."})
    blueprint, _, _ = found

    valid_harnesses = ["antigravity", "claude_code", "opencode"]
    if harness not in valid_harnesses:
        return json.dumps(
            {"status": "error", "message": f"Invalid harness `{harness}`. Must be one of {valid_harnesses}."}
        )

    out_dir = Path(target_workspace_dir) if target_workspace_dir else ROOT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    compilation = compile_architecture(
        blueprint=blueprint,
        harness=harness,  # type: ignore
        workspace_dir=str(out_dir),
    )

    deploy_compiled_files(compilation, out_dir)

    return json.dumps(
        {
            "status": "success",
            "blueprint_id": blueprint.metadata.id,
            "harness": harness,
            "target_workspace": str(out_dir.resolve()),
            "files_count": len(compilation.files),
            "deployed_files": [f.relative_path for f in compilation.files],
        },
        indent=2,
    )


@mcp_server.tool()
def create_benchmark_task(
    task_id: str,
    name: str,
    description: str,
    prompt: str,
    verifiers_json: str = "[]",
    workspace_source: str = "",
    rubric_dimensions_json: str = "[]",
) -> str:
    """Create a new evaluation benchmark task with deterministic verifiers and LLM judge rubrics.

    Args:
        task_id: Unique task identifier (e.g. 'financial-anomaly-triage').
        name: Human-readable task name.
        description: Summary of what the task evaluates.
        prompt: Initial prompt given to the agent architecture.
        verifiers_json: JSON array of VerificationCheck dicts (e.g. pytest_pass, file_exists, command_exit_code).
        workspace_source: Optional template workspace path for the task sandbox.
        rubric_dimensions_json: Optional JSON array of RubricDimension dicts for LLM Judge.

    Returns:
        JSON string confirming task creation, file path, and verification checks.
    """
    _ensure_backend_ready()
    clean_id = re.sub(r"[^a-z0-9_-]+", "-", task_id.strip().lower()).strip("-")

    # Parse verifiers
    raw_verifiers: List[Dict[str, Any]] = []
    if verifiers_json.strip():
        try:
            raw_verifiers = json.loads(verifiers_json)
        except Exception as exc:
            return json.dumps({"status": "error", "message": f"Invalid verifiers_json: {exc}"})

    checks: List[VerificationCheck] = []
    for idx, v in enumerate(raw_verifiers):
        check_id = v.get("id", f"check_{idx+1}")
        check_name = v.get("name", check_id.replace("_", " ").title())
        check_type = v.get("type", "command_exit_code")
        checks.append(
            VerificationCheck(
                id=check_id,
                name=check_name,
                type=check_type,
                command=v.get("command"),
                target_path=v.get("target_path"),
                pattern=v.get("pattern"),
                max_lines=v.get("max_lines"),
                weight=float(v.get("weight", 1.0)),
                required=bool(v.get("required", True)),
                timeout_seconds=int(v.get("timeout_seconds", 60)),
            )
        )

    # Parse rubrics
    raw_rubrics: List[Dict[str, Any]] = []
    if rubric_dimensions_json.strip():
        try:
            raw_rubrics = json.loads(rubric_dimensions_json)
        except Exception:
            pass

    dimensions: List[RubricDimension] = [
        RubricDimension(
            id=r.get("id", f"rubric_{i+1}"),
            name=r.get("name", f"Dimension {i+1}"),
            description=r.get("description", ""),
            weight=float(r.get("weight", 1.0)),
        )
        for i, r in enumerate(raw_rubrics)
    ]

    task_spec = TaskSpec(
        api_version="harnessforge/v1",
        kind="TaskSpec",
        id=clean_id,
        name=name.strip(),
        description=description.strip(),
        prompt=prompt.strip(),
        workspace_source=workspace_source.strip() if workspace_source.strip() else "tasks/sample_repos/auth_service",
        verifiers=checks,
        rubric=dimensions,
    )

    saved_task, yaml_str, target_path = save_task(task_spec)
    return json.dumps(
        {
            "status": "success",
            "task_id": saved_task.id,
            "name": saved_task.name,
            "file_path": str(target_path),
            "verifiers_count": len(saved_task.verifiers),
            "rubrics_count": len(saved_task.rubric),
        },
        indent=2,
    )


@mcp_server.tool()
def run_benchmark_task(
    blueprint_id: str,
    task_id: str,
    harness: str = "antigravity",
    mode: str = "simulated_benchmark",
    custom_prompt_override: str = "",
) -> str:
    """Execute a benchmark task on a specific agent architecture.

    Runs in an isolated sandbox or target workspace, records telemetry, and triggers evaluation.

    Args:
        blueprint_id: Architecture blueprint ID.
        task_id: Benchmark task ID.
        harness: Target harness ('antigravity', 'claude_code', or 'opencode').
        mode: Execution mode ('simulated_benchmark', 'headless', 'interactive').
        custom_prompt_override: Optional override for the benchmark task prompt.

    Returns:
        JSON string with run ID, status, and sandbox path.
    """
    _ensure_backend_ready()
    found_bp = get_blueprint(blueprint_id)
    if not found_bp:
        return json.dumps({"status": "error", "message": f"Blueprint `{blueprint_id}` not found."})
    found_task = get_task(task_id)
    if not found_task:
        return json.dumps({"status": "error", "message": f"Task `{task_id}` not found."})

    harness_val = harness if harness in ["antigravity", "claude_code", "opencode"] else "antigravity"
    mode_val = mode if mode in ["simulated_benchmark", "headless", "interactive"] else "simulated_benchmark"

    try:
        run_record = asyncio.run(
            start_execution_run(
                architecture_id=blueprint_id,
                task_id=task_id,
                harness=harness_val,  # type: ignore
                mode=mode_val,  # type: ignore
                custom_prompt_override=custom_prompt_override or None,
            )
        )
        return json.dumps(
            {
                "status": "success",
                "run_id": run_record.id,
                "run_status": run_record.status,
                "harness": run_record.harness,
                "sandbox_path": run_record.sandbox_path,
            },
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"status": "error", "message": f"Execution failed: {exc}"})


@mcp_server.tool()
def evaluate_workspace_deliverables(
    target_workspace_dir: str,
    task_id: str = "",
    external_docs_dir: str = "",
) -> str:
    """Evaluate deliverables generated in a project directory against a benchmark task's verifiers.

    Computes deterministic verifier results (pytest, files, INVEST, markdown sections),
    analyzes telemetry, and returns a 4-layer evaluation scorecard.

    Args:
        target_workspace_dir: The project folder containing the generated deliverables.
        task_id: Optional benchmark task ID containing the test assertions and verifiers.
        external_docs_dir: Optional path to external governance or workshop documentation.

    Returns:
        JSON scorecard including overall composite score, pass/fail status per check, and metrics.
    """
    _ensure_backend_ready()
    from app.api.runs import EvaluateDirectoryRequest, api_evaluate_deployed_directory

    ws_path = Path(target_workspace_dir)
    if not ws_path.exists():
        return json.dumps({"status": "error", "message": f"Directory `{target_workspace_dir}` does not exist."})

    req = EvaluateDirectoryRequest(
        project_directory=str(ws_path),
        task_id=task_id or None,
        external_docs_directory=external_docs_dir or None,
    )

    try:
        run_record = asyncio.run(api_evaluate_deployed_directory(req))
        report = run_record.evaluation
        if not report:
            return json.dumps({"status": "partial", "run_id": run_record.id, "message": "Evaluated without report."})

        return json.dumps(
            {
                "status": "success",
                "run_id": run_record.id,
                "overall_composite_score": report.overall_composite_score,
                "deterministic_score": report.deterministic_score,
                "topology_adherence_pct": report.topology_adherence_pct,
                "efficiency_pct": report.efficiency_pct,
                "judge_score": report.judge_score,
                "verifiers": [
                    {
                        "name": vr.name,
                        "passed": vr.passed,
                        "weight": vr.weight,
                        "output": vr.output.strip() if vr.output else "",
                    }
                    for vr in report.verifier_results
                ],
            },
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"status": "error", "message": f"Evaluation failed: {exc}"})


@mcp_server.tool()
def get_advisor_recommendations(run_id: str) -> str:
    """Get AI Architecture Advisor improvement diagnoses and v2 YAML diff upgrades for an evaluation run.

    Args:
        run_id: The ID of an evaluated run.

    Returns:
        JSON string containing diagnoses, recommendations, and suggested blueprint modifications.
    """
    _ensure_backend_ready()
    try:
        sug = generate_advisor_suggestion(run_id)
        return json.dumps(
            {
                "status": "success",
                "run_id": run_id,
                "proposed_version": sug.proposed_version,
                "summary": sug.summary,
                "diagnoses": [
                    {
                        "target_component": d.target_component,
                        "severity": d.severity,
                        "finding": d.finding,
                        "recommendation": d.recommendation,
                    }
                    for d in sug.diagnoses
                ],
                "proposed_yaml": sug.proposed_yaml,
            },
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"status": "error", "message": f"Failed to generate advisor suggestions: {exc}"})


def main() -> None:
    """CLI Entry point for the HarnessForge FastMCP server."""
    import sys

    transport = "stdio"
    for arg in sys.argv[1:]:
        if arg.startswith("--transport="):
            transport = arg.split("=", 1)[1]
        elif arg == "--sse":
            transport = "sse"

    # Run the FastMCP server
    mcp_server.run(transport=transport)  # type: ignore


if __name__ == "__main__":
    main()
