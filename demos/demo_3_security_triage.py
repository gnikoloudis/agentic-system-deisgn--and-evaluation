"""Demo 3: Security & Bugfix Triage (Code-Graph + AST + Pytest) via HarnessForge MCP Tools.

Demonstrates:
1. Discovering code-graph MCP in the catalog.
2. Scaffolding the multi-agent security triage architecture via `describe_and_build_system`.
3. Validating and compiling the architecture for OpenCode & Antigravity.
4. Creating the security triage benchmark task with AST and pytest verifiers.
5. Simulating the security vulnerability remediation (timing-attack fix & open redirect sanitization) and evaluating via MCP.
"""

import json
from pathlib import Path
import sys

# Ensure backend is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.mcp.server import (
    compile_and_deploy_system,
    create_benchmark_task,
    describe_and_build_system,
    evaluate_workspace_deliverables,
    list_mcp_catalog,
    validate_and_save_blueprint,
)


def run_demo():
    print("=" * 80)
    print("DEMO 3: Security & Bugfix Triage (Code-Graph + AST + Pytest) via MCP")
    print("=" * 80)

    # 1. Discover code-graph in MCP catalog
    print("\n[Step 1] Querying MCP Catalog for Codebase Intelligence Tools...")
    catalog = json.loads(list_mcp_catalog())
    available = [s["id"] for s in catalog["mcp_servers"]]
    print(f"-> Available MCP Servers: {', '.join(available)}")
    assert "code-graph" in available

    # 2. Describe and build security architecture
    print("\n[Step 2] Describing & Building Security Triage Architecture via MCP...")
    build_raw = describe_and_build_system(
        description="Security bugfix triage team using code-graph MCP to inspect AST nodes, identify vulnerable code paths, and patch issues.",
        target_harness="opencode",
        topology_pattern="generator-verifier-loop",
        mcp_servers="code-graph",
        system_id="security-bugfix-triage",
        system_name="Security & Bugfix Triage System (Code-Graph + AST + Pytest)",
    )
    build_res = json.loads(build_raw)
    print(f"-> Blueprint Generated: {build_res['blueprint_id']} ({build_res['name']})")
    print(f"-> Security Subagents: {', '.join(build_res['subagents'])}")
    print(f"-> Assigned MCPs: {', '.join(build_res['mcp_servers'])}")

    # 3. Validate and save
    print("\n[Step 3] Validating and Persisting Blueprint YAML...")
    save_res = json.loads(validate_and_save_blueprint(build_res["yaml"]))
    print(f"-> Saved Blueprint to: {save_res['file_path']}")

    # 4. Compile and deploy
    deploy_dir = Path(__file__).resolve().parent.parent / ".harness-workspaces" / "demo3_security_workspace"
    deploy_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[Step 4] Compiling and Deploying to Workspace: {deploy_dir}...")
    deploy_res = json.loads(
        compile_and_deploy_system(
            blueprint_id="security-bugfix-triage",
            harness="opencode",
            target_workspace_dir=str(deploy_dir),
        )
    )
    print(f"-> Deployed {deploy_res['files_count']} Native Config Files:")
    for f in deploy_res["deployed_files"][:5]:
        print(f"   • {f}")

    # 5. Create Benchmark Task via MCP
    print("\n[Step 5] Authoring Security Benchmark Task with AST & Pytest Verifiers via MCP...")
    verifiers = [
        {
            "id": "check_secure_hmac_used",
            "name": "Constant-Time Comparison Implemented",
            "type": "file_contains_regex",
            "target_path": "auth.py",
            "pattern": "compare_digest",
            "weight": 2.0,
            "required": True,
        },
        {
            "id": "check_redirect_sanitized",
            "name": "Open Redirect Vulnerability Patched",
            "type": "file_contains_regex",
            "target_path": "auth.py",
            "pattern": "startswith",
            "weight": 2.0,
            "required": True,
        },
        {
            "id": "check_pytest_security_pass",
            "name": "Security Test Suite Passes",
            "type": "pytest_pass",
            "command": "pytest -v test_auth.py",
            "weight": 4.0,
            "required": True,
        },
    ]
    task_res = json.loads(
        create_benchmark_task(
            task_id="security-ast-bugfix-triage",
            name="Security AST Vulnerability Triage & Patch Benchmark",
            description="Evaluates security team using code-graph MCP for AST search and call-graph traversal to locate and patch auth vulnerability.",
            prompt="Inspect auth.py using code-graph. Patch timing leak and open redirect. Run pytest.",
            verifiers_json=json.dumps(verifiers),
            workspace_source="tasks/sample_repos/vulnerable_auth_api",
        )
    )
    print(f"-> Task Created: {task_res['task_id']} with {task_res['verifiers_count']} verifiers.")

    # 6. Simulate security remediation in workspace:
    # Phase A: Security Patch Engineer writes patched auth.py
    secured_auth_code = """
\"\"\"Secured Authentication & Redirect Module.\"\"\"
import hmac
from typing import Optional
from urllib.parse import urlparse

MASTER_SECRET = "sk-live-production-secret-998811"

def validate_api_key(provided_key: str) -> bool:
    \"\"\"Constant-time token validation to prevent side-channel timing leaks.\"\"\"
    if not provided_key or not isinstance(provided_key, str):
        return False
    return hmac.compare_digest(provided_key, MASTER_SECRET)

def sanitize_redirect_url(url: str, allowed_host: str = "example.com") -> Optional[str]:
    \"\"\"Strict host validation preventing open-redirect exploitation.\"\"\"
    if not url:
        return None
    try:
        parsed = urlparse(url)
        # Enforce scheme and exact hostname
        if parsed.scheme in ("http", "https") and (parsed.netloc == allowed_host or parsed.netloc.startswith(f"{allowed_host}:")):
            return url
    except Exception:
        return None
    return None
"""
    (deploy_dir / "auth.py").write_text(secured_auth_code.strip(), encoding="utf-8")

    # Phase B: Regression Security Verifier ensures test_auth.py passes
    test_auth_code = """
import pytest
from auth import validate_api_key, sanitize_redirect_url, MASTER_SECRET

def test_valid_api_key():
    assert validate_api_key(MASTER_SECRET) is True

def test_invalid_api_key():
    assert validate_api_key("wrong-key-1234") is False

def test_open_redirect_bypass_blocked():
    evil_url = "https://attacker.com/steal?token=1&fake=example.com"
    assert sanitize_redirect_url(evil_url, "example.com") is None

def test_legitimate_redirect_allowed():
    valid_url = "https://example.com/dashboard"
    assert sanitize_redirect_url(valid_url, "example.com") == valid_url
"""
    (deploy_dir / "test_auth.py").write_text(test_auth_code.strip(), encoding="utf-8")

    # 7. Evaluate workspace
    print("\n[Step 6] Evaluating Security Deliverables against Benchmark Task via MCP...")
    eval_res = json.loads(
        evaluate_workspace_deliverables(
            target_workspace_dir=str(deploy_dir),
            task_id="security-ast-bugfix-triage",
        )
    )
    print(f"-> Evaluation Completed! Overall Composite Score: {eval_res.get('overall_composite_score', 'N/A')}/100")
    print(f"-> Deterministic Verifiers Score: {eval_res.get('deterministic_score', 'N/A')}%")
    for v in eval_res.get("verifiers", []):
        badge = "PASS" if v["passed"] else "FAIL"
        print(f"   [{badge}] {v['name']}")

    print("\n[SUCCESS] Demo 3 completed cleanly!")


if __name__ == "__main__":
    run_demo()
