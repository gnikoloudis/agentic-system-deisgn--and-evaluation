"""Comprehensive pytest suite for HarnessForge backend (Schemas, Storage, Multi-Harness Compilers, Sandbox, Runner, Evaluator, Advisor, API)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.compilers import compile_architecture
from app.db.database import init_db
from app.db.storage import get_blueprint, list_blueprints, list_tasks
from app.main import app


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_starter_blueprints_and_tasks_loaded():
    bps = list_blueprints()
    bp_ids = {b.metadata.id for b in bps}
    assert "solo-generalist" in bp_ids
    assert "planner-coder-verifier" in bp_ids
    assert "parallel-specialist-swarm" in bp_ids

    tasks = list_tasks()
    task_ids = {t.id for t in tasks}
    assert "bugfix-auth-token" in task_ids
    assert "feature-rate-limiter" in task_ids
    assert "refactor-order-pricing" in task_ids


@pytest.mark.parametrize("harness", ["claude_code", "antigravity", "opencode"])
def test_multi_harness_dual_mode_compiler(harness: str):
    found = get_blueprint("planner-coder-verifier")
    assert found is not None
    bp, _, _ = found

    compiled = compile_architecture(bp, harness=harness, run_id="test-compile-run")  # type: ignore[arg-type]
    paths = {f.relative_path for f in compiled.files}

    # Universal runtime topology state-machine & telemetry scripts must always be generated
    assert ".harness-eval/hook_runner.py" in paths
    assert ".harness-eval/topology_config.json" in paths
    assert ".harness-eval/state.json" in paths

    if harness == "claude_code":
        assert "CLAUDE.md" in paths
        assert ".claude/agents/planner.md" in paths
        assert ".claude/agents/coder.md" in paths
        assert ".claude/agents/verifier.md" in paths
        assert ".claude/settings.local.json" in paths
    elif harness == "antigravity":
        assert "GEMINI.md" in paths
        assert ".agents/rules/orchestrator.md" in paths
        assert ".agents/agents/planner.md" in paths
        assert ".agents/agents/coder.md" in paths
        assert ".agents/hooks.json" in paths
        assert ".agents/.harness-eval/hook_runner.py" in paths
    elif harness == "opencode":
        assert "AGENTS.md" in paths
        assert "opencode.json" in paths
        assert ".opencode/agent/planner.md" in paths
        assert ".opencode/plugin/harness_eval_telemetry.ts" in paths


def test_hook_runner_enforces_topology_and_permissions(tmp_path: Path):
    """Verify that .harness-eval/hook_runner.py blocks out-of-order subagent calls and unauthorized root writes."""
    found = get_blueprint("planner-coder-verifier")
    assert found is not None
    bp, _, _ = found
    bp.topology.enforcement_mode = "dual"
    bp.orchestrator.permissions.allow_write = False
    compiled = compile_architecture(bp, harness="claude_code", run_id="preview-run")

    for cf in compiled.files:
        dest = tmp_path / cf.relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(cf.content, encoding="utf-8")

    hook_script = tmp_path / ".harness-eval" / "hook_runner.py"

    # 1. Root orchestrator attempts direct Write (should be blocked with exit code 2 because allow_write=False)
    proc_write = subprocess.run(
        [sys.executable, str(hook_script), "PreToolUse"],
        cwd=str(tmp_path),
        input=json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "foo.py"}}),
        capture_output=True,
        text=True,
    )
    assert proc_write.returncode == 2
    assert "allow_write: false" in proc_write.stderr

    # 2. Root orchestrator attempts to call `coder` (Step 2) BEFORE required `planner` (Step 1) -> blocked with exit code 2
    proc_order = subprocess.run(
        [sys.executable, str(hook_script), "PreToolUse"],
        cwd=str(tmp_path),
        input=json.dumps({"tool_name": "Task", "tool_input": {"subagent_type": "coder"}}),
        capture_output=True,
        text=True,
    )
    assert proc_order.returncode == 2
    assert "Out-of-order subagent call blocked" in proc_order.stderr

    # 3. Calling `planner` (Step 1) succeeds with exit code 0
    proc_plan = subprocess.run(
        [sys.executable, str(hook_script), "PreToolUse"],
        cwd=str(tmp_path),
        input=json.dumps({"tool_name": "Task", "tool_input": {"subagent_type": "planner"}}),
        capture_output=True,
        text=True,
    )
    assert proc_plan.returncode == 0


def test_end_to_end_api_run_evaluation_ab_compare_and_advisor(client: TestClient):
    # 1. Run `solo-generalist` on `bugfix-auth-token`
    resp1 = client.post(
        "/api/runs",
        json={
            "architecture_id": "solo-generalist",
            "task_id": "bugfix-auth-token",
            "harness": "claude_code",
            "mode": "simulated_benchmark",
            "auto_evaluate": True,
        },
    )
    assert resp1.status_code == 200
    run1_id = resp1.json()["id"]

    # Trigger explicit evaluation to ensure report is ready synchronously
    ev1_resp = client.post(f"/api/evaluations/runs/{run1_id}/evaluate")
    assert ev1_resp.status_code == 200
    ev1 = ev1_resp.json()
    assert ev1["deterministic_score"] == 100.0
    assert ev1["all_required_verifiers_passed"] is True

    # 2. Run `planner-coder-verifier` on `bugfix-auth-token` with `antigravity`
    resp2 = client.post(
        "/api/runs",
        json={
            "architecture_id": "planner-coder-verifier",
            "task_id": "bugfix-auth-token",
            "harness": "antigravity",
            "mode": "simulated_benchmark",
            "auto_evaluate": True,
        },
    )
    assert resp2.status_code == 200
    run2_id = resp2.json()["id"]
    ev2_resp = client.post(f"/api/evaluations/runs/{run2_id}/evaluate")
    assert ev2_resp.status_code == 200
    ev2 = ev2_resp.json()
    assert ev2["deterministic_score"] == 100.0
    assert ev2["topology_adherence_pct"] == 100.0
    bp2 = get_blueprint("planner-coder-verifier")[0]
    assert len(ev2["trajectory"]["per_node_breakdown"]) == 1 + len(bp2.subagents)

    # 3. Side-by-Side A/B Comparison
    cmp_resp = client.post("/api/evaluations/compare", json={"run_ids": [run1_id, run2_id]})
    assert cmp_resp.status_code == 200
    cmp_data = cmp_resp.json()
    assert cmp_data["winner_run_id"] in (run1_id, run2_id)
    assert len(cmp_data["key_takeaways"]) >= 1

    # 4. AI Architecture Advisor generates actionable v2 YAML patch for solo-generalist
    adv_resp = client.get(f"/api/evaluations/runs/{run1_id}/advisor")
    assert adv_resp.status_code == 200
    adv_data = adv_resp.json()
    assert adv_data["proposed_version"] == "1.1.0"
    assert len(adv_data["diagnoses"]) >= 1
    assert "verifier" in adv_data["unified_yaml_diff"]

    # 5. Formatted Plain-Text Execution Log endpoint & Single Run Deletion
    log_resp = client.get(f"/api/runs/{run1_id}/log")
    assert log_resp.status_code == 200
    assert "HARNESSFORGE EXECUTION LOG" in log_resp.json()["log"]

    del_resp = client.delete(f"/api/runs/{run1_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True


def test_deploy_and_evaluate_specific_project_directory(client: TestClient, tmp_path: Path):
    """Verify deploying an architecture to a project folder, evaluating that folder, and generating project-specific Advisor improvements."""
    # 1. Export `technical-business-analyst` for `opencode` into a specific project directory
    exp_resp = client.post(
        "/api/blueprints/technical-business-analyst/export",
        json={
            "harness": "opencode",
            "target_directory": str(tmp_path),
            "task_id": "tba-focusflow-todo-app",
        },
    )
    assert exp_resp.status_code == 200
    exp_data = exp_resp.json()
    assert exp_data["exported"] is True
    assert (tmp_path / ".opencode" / "command" / "evaluate-project.md").exists()

    # 2. Evaluate the deployed project directory before deliverables are created -> Advisor diagnoses missing project deliverables & skipped subagents
    eval_dir_resp = client.post(
        "/api/runs/evaluate-directory",
        json={
            "project_directory": str(tmp_path),
            "task_id": "tba-focusflow-todo-app",
            "architecture_id": "technical-business-analyst",
            "harness": "opencode",
        },
    )
    assert eval_dir_resp.status_code == 200
    run_data = eval_dir_resp.json()
    run_id = run_data["id"]
    assert run_data["evaluation"] is not None

    adv_resp = client.get(f"/api/evaluations/runs/{run_id}/advisor?regenerate=true")
    assert adv_resp.status_code == 200
    adv_data = adv_resp.json()
    assert len(adv_data["diagnoses"]) >= 2
    assert any("verifier:" in d["target_component"] for d in adv_data["diagnoses"])


def test_rename_and_delete_architecture_blueprint(client: TestClient):
    """Verify cloning, renaming, and deleting an architecture blueprint via the REST API."""
    orig = client.get("/api/blueprints/solo-generalist").json()["blueprint"]
    orig["metadata"]["id"] = "temp-custom-blueprint"
    orig["metadata"]["name"] = "Temp Custom Blueprint v1"

    create_resp = client.post("/api/blueprints", json={"blueprint": orig})
    assert create_resp.status_code == 200
    assert create_resp.json()["blueprint"]["metadata"]["name"] == "Temp Custom Blueprint v1"

    # Rename the blueprint
    orig["metadata"]["name"] = "Renamed Enterprise Blueprint"
    rename_resp = client.post("/api/blueprints", json={"blueprint": orig})
    assert rename_resp.status_code == 200
    assert rename_resp.json()["blueprint"]["metadata"]["name"] == "Renamed Enterprise Blueprint"

    # Delete the blueprint
    del_resp = client.delete("/api/blueprints/temp-custom-blueprint")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True
    assert client.get("/api/blueprints/temp-custom-blueprint").status_code == 404


def test_enterprise_openai_compatible_provider_opencode(client: TestClient):
    """Verify Enterprise OpenAI-compatible provider config registers models and compiles into opencode.json."""
    orig_cfg = client.get("/api/runs/harnesses/models").json()
    try:
        test_provider = {
            "id": "acme-gateway",
            "name": "Acme Enterprise LLM",
            "protocol": "openai_compatible",
            "base_url": "https://llm.acme.internal/v1",
            "api_key_env": "ACME_LLM_API_KEY",
            "headers": {"X-Tenant-Id": "eng-platform"},
            "models": [{"id": "gpt-4o-enterprise", "name": "GPT-4o Enterprise", "tier": "coding"}],
            "enabled": True,
        }
        put_resp = client.put(
            "/api/runs/harnesses/models",
            json={"custom_providers": [*orig_cfg.get("custom_providers", []), test_provider]},
        )
        assert put_resp.status_code == 200
        updated = put_resp.json()
        assert any(m["id"] == "acme-gateway/gpt-4o-enterprise" for m in updated["native_models"]["opencode"])

        comp_resp = client.get("/api/blueprints/planner-coder-verifier/compile/opencode")
        assert comp_resp.status_code == 200
        oc_file = next(f for f in comp_resp.json()["files"] if f["relative_path"] == "opencode.json")
        oc_json = json.loads(oc_file["content"])
        assert "provider" in oc_json
        assert "acme-gateway" in oc_json["provider"]
        prov_out = oc_json["provider"]["acme-gateway"]
        assert prov_out["npm"] == "@ai-sdk/openai-compatible"
        assert prov_out["options"]["baseURL"] == "https://llm.acme.internal/v1"
        assert prov_out["options"]["apiKey"] == "{env:ACME_LLM_API_KEY}"
        assert prov_out["options"]["headers"]["X-Tenant-Id"] == "eng-platform"
        assert "gpt-4o-enterprise" in prov_out["models"]
    finally:
        client.put(
            "/api/runs/harnesses/models",
            json={
                "tier_map": orig_cfg["tier_map"],
                "native_models": orig_cfg["native_models"],
                "custom_providers": orig_cfg.get("custom_providers", []),
            },
        )


def test_folder_backed_skill_bundles_references_and_scripts(client: TestClient, tmp_path: Path):
    """Verify folder-backed skills (`source_dir`) inspect frontmatter and bundle references/scripts/assets across all 3 harnesses."""
    skill_dir = tmp_path / "react-expert"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "assets").mkdir(parents=True)

    (skill_dir / "SKILL.md").write_text(
        "---\nname: react-expert\ndescription: React 19 specialist skill\n---\n\n# React Expert\nUse references/server-components.md.\n",
        encoding="utf-8",
    )
    (skill_dir / "references" / "server-components.md").write_text("# RSC Guide\n", encoding="utf-8")
    (skill_dir / "scripts" / "check.py").write_text("print('ok')\n", encoding="utf-8")
    (skill_dir / "assets" / "logo.svg").write_text("<svg></svg>\n", encoding="utf-8")

    # 1. Inspect endpoint parses frontmatter & counts
    insp = client.post("/api/blueprints/inspect-skill-dir", json={"source_dir": str(skill_dir)})
    assert insp.status_code == 200
    info = insp.json()
    assert info["id"] == "react-expert"
    assert info["description"] == "React 19 specialist skill"
    assert info["counts"]["references"] == 1
    assert info["counts"]["scripts"] == 1
    assert info["counts"]["assets"] == 1

    # 2. Compiling across all 3 harnesses preserves SKILL.md + references/ + scripts/ + assets/
    from app.schemas.blueprint import SkillSpec

    found = get_blueprint("solo-generalist")
    assert found is not None
    bp = found[0].model_copy(deep=True)
    bp.skills.append(
        SkillSpec(
            id="react-expert",
            name="React Expert",
            description="React 19 specialist skill",
            source_dir=str(skill_dir),
        )
    )

    for harness, prefix in (
        ("claude_code", ".claude/skills/react-expert"),
        ("antigravity", ".agents/skills/react-expert"),
        ("opencode", ".opencode/skills/react-expert"),
    ):
        comp = compile_architecture(bp, harness=harness, run_id="skill-bundle-test")  # type: ignore[arg-type]
        paths = {f.relative_path for f in comp.files}
        assert f"{prefix}/SKILL.md" in paths
        assert f"{prefix}/references/server-components.md" in paths
        assert f"{prefix}/scripts/check.py" in paths
        assert f"{prefix}/assets/logo.svg" in paths

    # 3. Placeholder ID (e.g. `ba-template-2`) with source_dir pointing to `react-expert` must compile to `react-expert`, NOT `ba-template-2`
    bp_placeholder = found[0].model_copy(deep=True)
    bp_placeholder.skills.append(
        SkillSpec(
            id="ba-template-2",
            name="Custom BA Template 2",
            description="Placeholder",
            source_dir=str(skill_dir),
        )
    )
    inline_resp = client.post(
        "/api/blueprints/compile-preview",
        json={"blueprint": bp_placeholder.model_dump(mode="json"), "harness": "antigravity"},
    )
    assert inline_resp.status_code == 200
    inline_paths = {f["relative_path"] for f in inline_resp.json()["files"]}
    assert ".agents/skills/react-expert/SKILL.md" in inline_paths
    assert ".agents/skills/react-expert/references/server-components.md" in inline_paths
    assert ".agents/skills/ba-template-2/SKILL.md" not in inline_paths


def test_custom_user_commands_compile_across_all_harnesses():
    """Verify blueprint.commands compile to native slash commands/skills in OpenCode, Claude Code, and Antigravity."""
    from app.schemas.blueprint import CommandSpec

    found = get_blueprint("planner-coder-verifier")
    assert found is not None
    bp = found[0].model_copy(deep=True)
    bp.commands.append(
        CommandSpec(
            id="build-ui-epic",
            description="Build the next UI epic from external specs",
            prompt="Read external UI specs and implement EPIC-UI-01 via planner -> coder -> verifier.",
            agent="root_orchestrator",
        )
    )

    oc = compile_architecture(bp, harness="opencode", run_id="cmd-test")
    cc = compile_architecture(bp, harness="claude_code", run_id="cmd-test")
    ag = compile_architecture(bp, harness="antigravity", run_id="cmd-test")

    assert ".opencode/command/build-ui-epic.md" in {f.relative_path for f in oc.files}
    assert ".claude/commands/build-ui-epic.md" in {f.relative_path for f in cc.files}
    assert ".agents/skills/build-ui-epic/SKILL.md" in {f.relative_path for f in ag.files}


def test_issue_1_orphan_guardrail_removal_and_issue_2_agent_id_rename(tmp_path: Path):
    """Verify Issue #1 (orphan guardrail hook removal) and Issue #2 (custom orchestrator/subagent ID rename & runtime enforcement)."""
    found = get_blueprint("planner-coder-verifier")
    assert found is not None
    bp = found[0].model_copy(deep=True)

    # Issue #2: Rename Root Orchestrator ID to `pm_meeting_orchestrator` and subagent `planner` -> `meeting_analyst`
    old_orch = bp.orchestrator.id
    bp.orchestrator.id = "pm_meeting_orchestrator"
    bp.orchestrator.permissions.allow_write = False
    bp.topology.enforcement_mode = "dual"
    bp.topology.entry_node = "pm_meeting_orchestrator"
    for sa in bp.subagents:
        if sa.id == "planner":
            sa.id = "meeting_analyst"
    for edge in bp.topology.edges:
        if edge.source == old_orch:
            edge.source = "pm_meeting_orchestrator"
        if edge.target == "planner":
            edge.target = "meeting_analyst"
        if edge.source == "planner":
            edge.source = "meeting_analyst"

    # Issue #1: Remove all guardrail hooks (simulating deleting an orphan hook after edges were deleted)
    bp.hooks = []

    # Compile across all 3 harnesses and verify renamed orchestrator & subagent IDs propagate cleanly
    oc = compile_architecture(bp, harness="opencode", run_id="rename-test")
    cc = compile_architecture(bp, harness="claude_code", run_id="rename-test")
    ag = compile_architecture(bp, harness="antigravity", run_id="rename-test")

    assert ".opencode/agent/pm_meeting_orchestrator.md" in {f.relative_path for f in oc.files}
    assert ".opencode/agent/meeting_analyst.md" in {f.relative_path for f in oc.files}
    assert ".claude/agents/meeting_analyst.md" in {f.relative_path for f in cc.files}
    assert ".agents/agents/meeting_analyst.md" in {f.relative_path for f in ag.files}

    # Verify hook_runner.py enforces allow_write=False under the renamed orchestrator ID `pm_meeting_orchestrator`
    for cf in cc.files:
        dest = tmp_path / cf.relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(cf.content, encoding="utf-8")

    hook_script = tmp_path / ".harness-eval" / "hook_runner.py"
    proc_write = subprocess.run(
        [sys.executable, str(hook_script), "PreToolUse"],
        cwd=str(tmp_path),
        input=json.dumps({"tool_name": "Write", "tool_input": {"file_path": "notes.md"}}),
        capture_output=True,
        text=True,
    )
    assert proc_write.returncode == 2
    assert "pm_meeting_orchestrator" in proc_write.stderr
    assert "allow_write: false" in proc_write.stderr


def test_issue_3_create_deploy_evaluate_and_delete_custom_benchmark_task(client: TestClient, tmp_path: Path):
    """Verify Issue #3: creating custom evaluation benchmark tasks for diverse agentic designs (e.g. product-management / frontend-ui) and evaluating a project against them."""
    task_id = "test-pm-meeting-eval"
    custom_task = {
        "id": task_id,
        "name": "PM Meeting Notes Synthesis Evaluation",
        "category": "product-management",
        "difficulty": "medium",
        "description": "Verifies PM meeting synthesis deliverables.",
        "prompt": "Synthesize meeting notes into MEETING_SUMMARY.md.",
        "workspace_source": str(tmp_path),
        "expected_subagents": ["meeting_analyst"],
        "verifiers": [
            {
                "id": "summary_exists",
                "name": "MEETING_SUMMARY.md exists",
                "type": "file_exists",
                "target_path": "MEETING_SUMMARY.md",
                "weight": 1.0,
                "required": True,
                "timeout_seconds": 10,
            },
            {
                "id": "pm_sections",
                "name": "Required PM Sections Present",
                "type": "markdown_sections_present",
                "target_path": "MEETING_SUMMARY.md",
                "pattern": "Executive Summary,Decisions,Action Items",
                "weight": 2.0,
                "required": True,
                "timeout_seconds": 15,
            },
        ],
        "tags": ["product-management", "no-code"],
    }
    try:
        # 1. Create custom benchmark task via API
        create_resp = client.post("/api/tasks", json={"task": custom_task})
        assert create_resp.status_code == 200
        assert create_resp.json()["task"]["id"] == task_id
        assert create_resp.json()["task"]["category"] == "product-management"

        # 2. Write deliverable in tmp_path and evaluate project folder using the new custom benchmark task
        (tmp_path / "MEETING_SUMMARY.md").write_text(
            "# Meeting Summary\n\n## Executive Summary\nAligned on Q4 launch.\n\n## Decisions\nApproved React 19 UI.\n\n## Action Items\n- Ship MVP.\n",
            encoding="utf-8",
        )
        eval_resp = client.post(
            "/api/runs/evaluate-directory",
            json={
                "project_directory": str(tmp_path),
                "task_id": task_id,
                "architecture_id": "solo-generalist",
                "harness": "antigravity",
            },
        )
        assert eval_resp.status_code == 200
        ev = eval_resp.json()["evaluation"]
        assert ev["deterministic_score"] == 100.0
        assert ev["all_required_verifiers_passed"] is True
    finally:
        del_resp = client.delete(f"/api/tasks/{task_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] is True


def test_issue_4_mcp_server_assignments_and_three_harness_examples():
    """Verify Issue #4: per-agent MCP server assignments & all 3 example blueprints (Antigravity, Claude Code, OpenCode)."""
    # 1. Antigravity example
    agy_tuple = get_blueprint("mcp-antigravity-fullstack-studio")
    assert agy_tuple is not None
    agy_comp = compile_architecture(agy_tuple[0], harness="antigravity", run_id="mcp-agy-test")
    agy_files = {f.relative_path: f.content for f in agy_comp.files}
    assert ".agents/mcp_config.json" in agy_files
    agy_mcp = json.loads(agy_files[".agents/mcp_config.json"])["mcpServers"]
    assert "code-graph" in agy_mcp and agy_mcp["code-graph"]["command"] == "npx"
    assert agy_mcp["stitch"]["serverUrl"] == "https://stitch.googleapis.com/mcp"
    assert "enable_mcp_tools: true" in agy_files[".agents/agents/codebase_architect.md"]
    assert "enable_mcp_tools: false" in agy_files[".agents/agents/qa_verifier.md"]

    # 2. Claude Code example
    cc_tuple = get_blueprint("mcp-claude-code-security-ops")
    assert cc_tuple is not None
    cc_comp = compile_architecture(cc_tuple[0], harness="claude_code", run_id="mcp-cc-test")
    cc_files = {f.relative_path: f.content for f in cc_comp.files}
    assert ".mcp.json" in cc_files
    cc_mcp = json.loads(cc_files[".mcp.json"])["mcpServers"]
    assert "github" in cc_mcp and cc_mcp["sentry"]["type"] == "sse"
    assert "mcp__sentry__*" in cc_files[".claude/agents/sentry_triager.md"]
    assert "mcp__filesystem__*" not in cc_files[".claude/agents/sentry_triager.md"]
    assert "mcp__github__*" in cc_files[".claude/agents/security_reviewer.md"]

    # 3. OpenCode example
    oc_tuple = get_blueprint("mcp-opencode-data-platform")
    assert oc_tuple is not None
    oc_comp = compile_architecture(oc_tuple[0], harness="opencode", run_id="mcp-oc-test")
    oc_files = {f.relative_path: f.content for f in oc_comp.files}
    oc_json = json.loads(oc_files["opencode.json"])
    assert oc_json["mcp"]["context7"]["type"] == "remote"
    assert oc_json["mcp"]["postgres"]["type"] == "local"
    assert oc_json["agent"]["e2e_qa_tester"]["tools"]["playwright*"] is True
    assert oc_json["agent"]["e2e_qa_tester"]["tools"]["postgres*"] is False
    assert oc_json["agent"]["data_engineer"]["tools"]["postgres*"] is True
    assert oc_json["agent"]["data_engineer"]["tools"]["playwright*"] is False


def test_issue_5_blocking_run_preflight_and_stale_cleanup(client: TestClient):
    """Verify Issue #5: preliminary pre-flight checks, single-flight blocking concurrency guard, and stale evaluation cleanup."""
    from app.db.database import save_run, utc_now_iso
    from app.runner import executor
    from app.schemas.evaluation import RunRecordSchema

    # 1. Pre-flight check passes for valid blueprint & task
    pf_ok = client.post(
        "/api/runs/preflight",
        json={
            "architecture_id": "solo-generalist",
            "task_id": "bugfix-auth-token",
            "harness": "claude_code",
            "mode": "simulated_benchmark",
        },
    )
    assert pf_ok.status_code == 200
    pf_ok_data = pf_ok.json()
    assert pf_ok_data["ready"] is True
    assert pf_ok_data["active_run_id"] is None
    assert all(c["status"] != "fail" for c in pf_ok_data["checks"])

    # 2. Pre-flight check fails for missing blueprint or missing task
    pf_bad = client.post(
        "/api/runs/preflight",
        json={
            "architecture_id": "nonexistent-arch-xyz",
            "task_id": "nonexistent-task-xyz",
            "harness": "claude_code",
            "mode": "simulated_benchmark",
        },
    )
    assert pf_bad.status_code == 200
    pf_bad_data = pf_bad.json()
    assert pf_bad_data["ready"] is False
    failed_ids = {c["id"] for c in pf_bad_data["checks"] if c["status"] == "fail"}
    assert "blueprint_valid" in failed_ids
    assert "task_workspace" in failed_ids

    # 3. Single-flight blocking concurrency lock returns 409 Conflict while another run is active
    fake_active_id = "run-active-lock-test"
    with executor._run_registry_lock:
        executor._starting_run_ids.add(fake_active_id)
    try:
        active_resp = client.get("/api/runs/active")
        assert active_resp.status_code == 200
        assert active_resp.json()["has_active_run"] is True
        assert active_resp.json()["active_run"]["id"] == fake_active_id

        pf_blocked = client.post(
            "/api/runs/preflight",
            json={
                "architecture_id": "solo-generalist",
                "task_id": "bugfix-auth-token",
                "harness": "claude_code",
                "mode": "simulated_benchmark",
            },
        )
        assert pf_blocked.status_code == 200
        assert pf_blocked.json()["ready"] is False
        assert pf_blocked.json()["active_run_id"] == fake_active_id

        conflict_resp = client.post(
            "/api/runs",
            json={
                "architecture_id": "solo-generalist",
                "task_id": "bugfix-auth-token",
                "harness": "claude_code",
                "mode": "simulated_benchmark",
                "auto_evaluate": False,
            },
        )
        assert conflict_resp.status_code == 409
        assert fake_active_id in conflict_resp.json()["detail"]

        del_active_resp = client.delete(f"/api/runs/{fake_active_id}")
        assert del_active_resp.status_code == 409
    finally:
        with executor._run_registry_lock:
            executor._starting_run_ids.discard(fake_active_id)

    assert client.get("/api/runs/active").json()["has_active_run"] is False

    # 4. Stale evaluation detection & cleanup (orphaned 'running' + 'cancelled' without evaluation)
    stale_running = RunRecordSchema(
        id="deploy-stale-running-1",
        architecture_id="solo-generalist",
        architecture_name="Solo Generalist",
        architecture_version="1.0.0",
        task_id="bugfix-auth-token",
        task_name="Stale Running Task",
        harness="claude_code",
        mode="simulated_benchmark",
        status="running",
        sandbox_path="",
        cli_command="claude",
        started_at=utc_now_iso(),
    )
    stale_cancelled = RunRecordSchema(
        id="deploy-stale-cancelled-2",
        architecture_id="solo-generalist",
        architecture_name="Solo Generalist",
        architecture_version="1.0.0",
        task_id="bugfix-auth-token",
        task_name="Stale Cancelled Task",
        harness="claude_code",
        mode="simulated_benchmark",
        status="cancelled",
        sandbox_path="",
        cli_command="claude",
        started_at=utc_now_iso(),
    )
    save_run(stale_running)
    save_run(stale_cancelled)

    clear_resp = client.delete("/api/runs/stale")
    assert clear_resp.status_code == 200
    clear_data = clear_resp.json()
    assert "deploy-stale-running-1" in clear_data["cleared_run_ids"]
    assert "deploy-stale-cancelled-2" in clear_data["cleared_run_ids"]
    assert clear_data["cleared_count"] >= 2

    # 5. Idempotent DELETE on already-missing stale run ID returns 200 (no 404 trap)
    ghost_del = client.delete("/api/runs/deploy-4c3e26a8")
    assert ghost_del.status_code == 200
    assert ghost_del.json()["deleted"] is False
    assert ghost_del.json()["already_missing"] is True


def test_issue_6_workflow_handoff_edges_normalization_and_compilation():
    """Verify Issue #6: reversed skill->agent edges are normalized, workflow handoffs are separated from skill assignments,
    and compiled markdown/subagents/topology_config reflect the true workflow design."""
    from app.schemas.blueprint import AgentArchitecture, TopologyEdge

    bp_tuple = get_blueprint("planner-coder-verifier")
    assert bp_tuple is not None
    bp = bp_tuple[0].model_copy(deep=True)

    # Inject a reversed Skill -> Agent edge (required=True, generic 'Step 7 handoff'), a duplicate, and a dangling edge
    bp.topology.edges.extend(
        [
            TopologyEdge(
                id="e_reversed_skill",
                source="diff-audit",
                target="coder",
                condition="Step 7 handoff",
                order=99,
                required=True,
                max_loops=3,
            ),
            TopologyEdge(
                id="e_dangling",
                source="ghost_agent",
                target="coder",
                condition="Broken",
                order=100,
                required=True,
                max_loops=1,
            ),
        ]
    )
    normalized = AgentArchitecture.model_validate(bp.model_dump())

    # 1. Agent-to-agent workflow handoffs are strictly numbered 1..N with zero skill or dangling edges
    wf_edges = normalized.workflow_handoff_edges()
    assert [e.order for e in wf_edges] == list(range(1, len(wf_edges) + 1))
    assert all(e.source != "diff-audit" and e.target != "diff-audit" for e in wf_edges)
    assert all(e.source != "ghost_agent" for e in wf_edges)

    # 2. Reversed skill->agent edge was flipped to coder -> diff-audit with required=False and clean condition
    sk_edges = normalized.skill_binding_edges()
    coder_skill_edge = next((e for e in sk_edges if e.source == "coder" and e.target == "diff-audit"), None)
    assert coder_skill_edge is not None
    assert coder_skill_edge.required is False
    assert coder_skill_edge.max_loops == 1
    assert coder_skill_edge.condition == "Applies /diff-audit"

    # 3. Compilation across all 3 harnesses keeps skills out of Mandatory Workflow Topology & topology_config.json,
    #    prints Assigned to in Section 5, and injects Assigned Skills into compiled subagent files
    for harness, root_doc, subagent_path in (
        ("antigravity", "GEMINI.md", ".agents/agents/coder.md"),
        ("claude_code", "CLAUDE.md", ".claude/agents/coder.md"),
        ("opencode", "AGENTS.md", ".opencode/agent/coder.md"),
    ):
        comp = compile_architecture(normalized, harness=harness, run_id="issue6-test")
        files_map = {f.relative_path: f.content for f in comp.files}
        root_md = files_map[root_doc]
        topo_section = root_md.split("## 4. Mandatory Workflow Topology")[1].split("## 5. Available Skills")[0]
        assert "diff-audit" not in topo_section
        skills_section = root_md.split("## 5. Available Skills")[1].split("## 6.")[0]
        assert "`coder`" in skills_section and "`diff-audit`" in skills_section

        assert "## Assigned Skills" in files_map[subagent_path]
        assert "`/diff-audit`" in files_map[subagent_path]

        topo_cfg = json.loads(files_map[".harness-eval/topology_config.json"])
        assert all(e["source"] != "diff-audit" and e["target"] != "diff-audit" for e in topo_cfg["edges"])

    # 4. SDLC (Custom) blueprint loads and compiles with zero skill-as-handoff corruption
    sdlc_tuple = get_blueprint("planner-coder-verifier-custom")
    if sdlc_tuple is not None:
        sdlc_bp = sdlc_tuple[0]
        sdlc_wf = sdlc_bp.workflow_handoff_edges()
        sdlc_skill_ids = {s.id for s in sdlc_bp.skills}
        assert all(e.source not in sdlc_skill_ids and e.target not in sdlc_skill_ids for e in sdlc_wf)
        assert [e.order for e in sdlc_wf] == list(range(1, len(sdlc_wf) + 1))


def test_generated_agent_files_match_canvas_details_and_omit_tba_for_non_tba():
    """Verify Generated Agent & Configuration Files include complete canvas agent details across all 3 harnesses
    and do NOT emit TBA-only commands for non-TBA blueprints."""
    sdlc_tuple = get_blueprint("planner-coder-verifier-custom")
    assert sdlc_tuple is not None
    sdlc_bp = sdlc_tuple[0].model_copy(deep=True)
    sdlc_bp.orchestrator.id = "sdlc_lead"
    sdlc_bp.orchestrator.permissions.allowed_commands = ["git status"]

    for harness, root_doc, verifier_path in (
        ("antigravity", "GEMINI.md", ".agents/agents/verifier.md"),
        ("claude_code", "CLAUDE.md", ".claude/agents/verifier.md"),
        ("opencode", "AGENTS.md", ".opencode/agent/verifier.md"),
    ):
        comp = compile_architecture(sdlc_bp, harness=harness, run_id="canvas-align-test")
        files_map = {f.relative_path: f.content for f in comp.files}

        # 1. Non-TBA blueprint must NOT emit generate-tba-pack or mention nonexistent TBA subagents
        assert not any("generate-tba-pack" in p for p in files_map)
        for path, content in files_map.items():
            if "verify-setup" in path or "evaluate-project" in path:
                assert "requirements_elicitor" not in content
                assert "WORKFLOWS_AND_DELIVERY_DOCS.md" not in content
                assert "sdlc_lead" in content

        # 2. Root doc includes orchestrator ID, role, tools, allowed_commands, and subagent max_turns & tools
        root_md = files_map[root_doc]
        assert "`sdlc_lead`" in root_md
        assert "`git status`" in root_md
        assert "Max Turns" in root_md

        # 3. Verifier subagent file includes max_turns, tools, allowed_commands (`pytest`), and assigned skills
        ver_md = files_map[verifier_path]
        assert "max_turns: 12" in ver_md
        assert "`pytest`" in ver_md
        assert "`/diff-audit`" in ver_md

        if harness == "claude_code":
            settings_json = json.loads(files_map[".claude/settings.local.json"])
            assert "Bash(pytest*)" in settings_json["permissions"]["allow"]
            assert "Bash(git status*)" in settings_json["permissions"]["allow"]
            assert "Bash(rm -rf /*)" in settings_json["permissions"]["deny"]
        elif harness == "opencode":
            oc_json = json.loads(files_map["opencode.json"])
            assert oc_json["agent"]["verifier"]["max_turns"] == 12
            assert oc_json["agent"]["verifier"]["tools"]["read"] is True
            assert "const orchId = cfg.orchestrator?.id" in files_map[".opencode/plugin/harness_eval_telemetry.ts"]
        elif harness == "antigravity":
            assert "allow_shell: true" in ver_md
            assert "`/diff-audit`" in root_md  # Included inside GEMINI.md define_subagent SystemPrompt too

    # 4. TBA blueprint DOES still emit generate-tba-pack for Antigravity and OpenCode
    tba_tuple = get_blueprint("technical-business-analyst")
    assert tba_tuple is not None
    tba_agy = compile_architecture(tba_tuple[0], harness="antigravity", run_id="tba-check")
    assert any("generate-tba-pack" in f.relative_path for f in tba_agy.files)
    tba_oc = compile_architecture(tba_tuple[0], harness="opencode", run_id="tba-check")
    assert any("generate-tba-pack" in f.relative_path for f in tba_oc.files)





