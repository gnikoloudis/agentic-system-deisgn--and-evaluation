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





