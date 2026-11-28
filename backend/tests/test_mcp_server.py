"""Comprehensive tests for the HarnessForge FastMCP Server and Catalog."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.mcp.catalog import (
    detect_host_mcp_servers,
    get_all_available_mcp_servers,
    get_mcp_presets,
    resolve_mcp_spec,
)
from app.mcp.server import (
    compile_and_deploy_system,
    create_benchmark_task,
    describe_and_build_system,
    evaluate_workspace_deliverables,
    get_advisor_recommendations,
    inspect_blueprint,
    list_blueprints_and_tasks,
    list_mcp_catalog,
    validate_and_save_blueprint,
)


def test_mcp_catalog_presets_and_detection(tmp_path: Path):
    """Test standard presets and host detection from a mock mcp.json."""
    presets = get_mcp_presets()
    preset_ids = {p.id for p in presets}
    assert "sqlite" in preset_ids
    assert "yahoofinance" in preset_ids
    assert "code-graph" in preset_ids
    assert "stitch" in preset_ids

    # Create mock host mcp.json
    mock_mcp = {
        "mcpServers": {
            "custom-test-mcp": {
                "command": "python",
                "args": ["-m", "test_server"],
                "env": {"TEST_VAR": "123"},
            }
        }
    }
    (tmp_path / "mcp.json").write_text(json.dumps(mock_mcp), encoding="utf-8")

    detected = detect_host_mcp_servers(tmp_path)
    assert any(s.id == "custom-test-mcp" for s in detected)

    all_servers = get_all_available_mcp_servers(tmp_path)
    all_ids = {s.id for s in all_servers}
    assert "custom-test-mcp" in all_ids
    assert "sqlite" in all_ids


def test_tool_list_mcp_catalog():
    """Test tool list_mcp_catalog returns JSON with expected servers."""
    res_raw = list_mcp_catalog()
    res = json.loads(res_raw)
    assert res["count"] > 0
    server_ids = [s["id"] for s in res["mcp_servers"]]
    assert "sqlite" in server_ids
    assert "yahoofinance" in server_ids
    assert "code-graph" in server_ids


def test_describe_and_build_system_financial():
    """Test describe_and_build_system with financial description and sqlite + yahoofinance MCPs."""
    res_raw = describe_and_build_system(
        description="Financial analysis team that ingests market data, analyzes price changes, and correlates with historical news using sqlite and yahoofinance.",
        target_harness="antigravity",
        topology_pattern="generator-verifier-loop",
        mcp_servers="sqlite, yahoofinance",
        system_id="test-financial-analyst",
        system_name="Test Financial Analyst Team",
    )
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert res["blueprint_id"] == "test-financial-analyst"
    assert "sqlite" in res["mcp_servers"]
    assert "yahoofinance" in res["mcp_servers"]
    assert len(res["subagents"]) >= 3
    assert "market_data_collector" in res["subagents"]
    assert "yaml" in res
    assert "kind: AgentArchitecture" in res["yaml"]


def test_describe_and_build_system_tdd():
    """Test describe_and_build_system with TDD workflow."""
    res_raw = describe_and_build_system(
        description="Complete TDD system that reads user stories, drafts failing tests first, develops implementation, and runs pytest verification.",
        target_harness="claude_code",
        topology_pattern="generator-verifier-loop",
        system_id="test-tdd-pipeline",
        system_name="Test TDD Pipeline",
    )
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert "test_suite_author" in res["subagents"]
    assert "feature_developer" in res["subagents"]
    assert "refactor_and_verifier" in res["subagents"]


def test_describe_and_build_system_security():
    """Test describe_and_build_system with security/bugfix triage and code-graph MCP."""
    res_raw = describe_and_build_system(
        description="Security bugfix triage team using code-graph MCP to inspect AST nodes, identify vulnerable code paths, and patch issues.",
        target_harness="opencode",
        topology_pattern="generator-verifier-loop",
        mcp_servers="code-graph",
        system_id="test-security-triage",
        system_name="Test Security Triage Team",
    )
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert "code-graph" in res["mcp_servers"]
    assert "code_graph_architect" in res["subagents"]


def test_validate_save_inspect_and_compile(tmp_path: Path):
    """Test the full lifecycle: describe -> validate & save -> inspect -> compile & deploy."""
    # 1. Build
    build_raw = describe_and_build_system(
        description="Lifecycle test system for verification.",
        target_harness="antigravity",
        topology_pattern="generator-verifier-loop",
        mcp_servers="sqlite",
        system_id="lifecycle-test-system",
    )
    build_res = json.loads(build_raw)
    yaml_content = build_res["yaml"]

    # 2. Validate and save
    save_raw = validate_and_save_blueprint(yaml_content)
    save_res = json.loads(save_raw)
    assert save_res["status"] == "success"
    assert save_res["blueprint_id"] == "lifecycle-test-system"

    # 3. Inspect
    inspect_raw = inspect_blueprint("lifecycle-test-system")
    inspect_res = json.loads(inspect_raw)
    assert inspect_res["id"] == "lifecycle-test-system"
    assert "yaml" in inspect_res

    # 4. List blueprints and tasks
    list_raw = list_blueprints_and_tasks()
    list_res = json.loads(list_raw)
    bp_ids = [b["id"] for b in list_res["blueprints"]]
    assert "lifecycle-test-system" in bp_ids

    # 5. Compile and deploy to tmp_path
    deploy_raw = compile_and_deploy_system(
        blueprint_id="lifecycle-test-system",
        harness="antigravity",
        target_workspace_dir=str(tmp_path),
    )
    deploy_res = json.loads(deploy_raw)
    assert deploy_res["status"] == "success"
    assert deploy_res["files_count"] > 0

    # Verify deployed files on disk
    assert (tmp_path / "GEMINI.md").exists()
    assert (tmp_path / "mcp.json").exists()
    mcp_json_content = json.loads((tmp_path / "mcp.json").read_text(encoding="utf-8"))
    assert "mcpServers" in mcp_json_content
    assert "sqlite" in mcp_json_content["mcpServers"]

    # 6. Cleanup test blueprint
    from app.db.storage import delete_blueprint
    delete_blueprint("lifecycle-test-system")


def test_create_benchmark_task(tmp_path: Path):
    """Test creating a benchmark task with verifiers and rubrics."""
    verifiers = [
        {
            "id": "test_output_exists",
            "name": "Deliverables Output File Exists",
            "type": "file_exists",
            "target_path": "report.json",
            "weight": 2.0,
            "required": True,
        },
        {
            "id": "pytest_pass",
            "name": "Unit Tests Pass",
            "type": "pytest_pass",
            "command": "pytest -v",
            "weight": 3.0,
            "required": True,
        },
    ]
    rubrics = [
        {
            "id": "accuracy",
            "name": "Factual Accuracy",
            "description": "Output is grounded in factual data without hallucination.",
            "weight": 1.5,
        }
    ]

    task_raw = create_benchmark_task(
        task_id="mcp-test-task",
        name="MCP Test Task",
        description="Benchmark task created via MCP server.",
        prompt="Analyze the dataset and generate report.json.",
        verifiers_json=json.dumps(verifiers),
        rubric_dimensions_json=json.dumps(rubrics),
    )
    task_res = json.loads(task_raw)
    assert task_res["status"] == "success"
    assert task_res["task_id"] == "mcp-test-task"
    assert task_res["verifiers_count"] == 2
    assert task_res["rubrics_count"] == 1

    # Cleanup test task
    from app.db.storage import delete_task
    delete_task("mcp-test-task")


def test_evaluate_workspace_deliverables_nonexistent():
    """Test evaluating a non-existent directory returns error cleanly."""
    res_raw = evaluate_workspace_deliverables("D:/non_existent_folder_xyz_123")
    res = json.loads(res_raw)
    assert res["status"] == "error"
    assert "does not exist" in res["message"]
