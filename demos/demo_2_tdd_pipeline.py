"""Demo 2: Complete TDD System (User Story to Tests & Code) via HarnessForge MCP Tools.

Demonstrates:
1. Calling `describe_and_build_system` to scaffold a multi-agent TDD team (Test Author -> Developer -> Refactor Verifier).
2. Saving and compiling the architecture for Claude Code & Antigravity.
3. Authoring the benchmark task with strict pytest verifiers.
4. Simulating the TDD implementation cycle (Red tests -> Green code) and evaluating with MCP tools.
"""

from decimal import Decimal
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
    validate_and_save_blueprint,
)


def run_demo():
    print("=" * 80)
    print("DEMO 2: Complete TDD System (User Story to Tests & Code) via MCP")
    print("=" * 80)

    # 1. Describe and build TDD system
    print("\n[Step 1] Describing & Building TDD Agent Architecture via MCP...")
    build_raw = describe_and_build_system(
        description="Complete TDD system that reads user stories, drafts failing tests first, develops implementation, and runs pytest verification.",
        target_harness="claude_code",
        topology_pattern="generator-verifier-loop",
        system_id="tdd-user-story-developer",
        system_name="TDD Multi-Agent System (User Story to Tests & Code)",
    )
    build_res = json.loads(build_raw)
    print(f"-> Blueprint Generated: {build_res['blueprint_id']} ({build_res['name']})")
    print(f"-> TDD Subagents: {', '.join(build_res['subagents'])}")

    # 2. Validate and save
    print("\n[Step 2] Validating and Persisting Blueprint YAML...")
    save_res = json.loads(validate_and_save_blueprint(build_res["yaml"]))
    print(f"-> Saved Blueprint to: {save_res['file_path']}")

    # 3. Compile and deploy
    deploy_dir = Path(__file__).resolve().parent.parent / ".harness-workspaces" / "demo2_tdd_workspace"
    deploy_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[Step 3] Compiling and Deploying to Workspace: {deploy_dir}...")
    deploy_res = json.loads(
        compile_and_deploy_system(
            blueprint_id="tdd-user-story-developer",
            harness="claude_code",
            target_workspace_dir=str(deploy_dir),
        )
    )
    print(f"-> Deployed {deploy_res['files_count']} Native Config Files:")
    for f in deploy_res["deployed_files"][:5]:
        print(f"   • {f}")

    # 4. Create Benchmark Task via MCP
    print("\n[Step 4] Authoring Benchmark Task with TDD Verifiers via MCP...")
    verifiers = [
        {
            "id": "check_test_file_exists",
            "name": "TDD Test Suite Authored",
            "type": "file_exists",
            "target_path": "tests/test_service.py",
            "weight": 2.0,
            "required": True,
        },
        {
            "id": "check_service_impl_exists",
            "name": "Production Service Implemented",
            "type": "file_exists",
            "target_path": "service.py",
            "weight": 2.0,
            "required": True,
        },
        {
            "id": "check_pytest_all_pass",
            "name": "Full Pytest Suite Passes",
            "type": "pytest_pass",
            "command": "pytest -v tests/test_service.py",
            "weight": 4.0,
            "required": True,
        },
    ]
    task_res = json.loads(
        create_benchmark_task(
            task_id="tdd-user-story-implementation",
            name="TDD User Story to Test Suite & Implementation Benchmark",
            description="Evaluates multi-agent TDD team receiving user story and writing tests first.",
            prompt="Read USER_STORIES.md, author tests in tests/test_service.py, implement service.py, run pytest.",
            verifiers_json=json.dumps(verifiers),
            workspace_source="tasks/sample_repos/tdd_calculator_service",
        )
    )
    print(f"-> Task Created: {task_res['task_id']} with {task_res['verifiers_count']} verifiers.")

    # 5. Simulate deliverables in workspace:
    # Phase A: Test Suite Author writes tests/test_service.py
    tests_dir = deploy_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    test_code = """
import pytest
from decimal import Decimal
from service import DiscountCalculator

def test_base_tier_no_discount():
    calc = DiscountCalculator()
    assert calc.calculate_discount(Decimal("50.00"), loyalty_status=None) == Decimal("0.00")

def test_tier_1_volume_discount():
    calc = DiscountCalculator()
    # 5% of 200 = 10.00
    assert calc.calculate_discount(Decimal("200.00"), loyalty_status=None) == Decimal("10.00")

def test_tier_2_volume_with_gold_loyalty():
    calc = DiscountCalculator()
    # 10% volume + 5% gold = 15% of 1000 = 150.00
    assert calc.calculate_discount(Decimal("1000.00"), loyalty_status="gold") == Decimal("150.00")

def test_max_discount_cap_at_twenty_percent():
    calc = DiscountCalculator()
    # 10% volume + 10% platinum = 20% max cap
    assert calc.calculate_discount(Decimal("1000.00"), loyalty_status="platinum") == Decimal("200.00")

def test_negative_subtotal_raises_value_error():
    calc = DiscountCalculator()
    with pytest.raises(ValueError, match="Subtotal must be non-negative"):
        calc.calculate_discount(Decimal("-10.00"), loyalty_status="gold")
"""
    (tests_dir / "test_service.py").write_text(test_code.strip(), encoding="utf-8")

    # Phase B: Feature Developer implements service.py
    service_code = """
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

class DiscountCalculator:
    \"\"\"Calculates order discounts based on volume tiers and customer loyalty status.\"\"\"

    def calculate_discount(self, subtotal: Decimal, loyalty_status: Optional[str] = None) -> Decimal:
        if subtotal < 0:
            raise ValueError("Subtotal must be non-negative")

        rate = Decimal("0.00")
        if Decimal("100.00") <= subtotal < Decimal("500.00"):
            rate += Decimal("0.05")
        elif subtotal >= Decimal("500.00"):
            rate += Decimal("0.10")

        if loyalty_status == "gold":
            rate += Decimal("0.05")
        elif loyalty_status == "platinum":
            rate += Decimal("0.10")

        # Cap at 20%
        rate = min(rate, Decimal("0.20"))

        discount = subtotal * rate
        return discount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
"""
    (deploy_dir / "service.py").write_text(service_code.strip(), encoding="utf-8")

    # 6. Evaluate workspace
    print("\n[Step 5] Evaluating TDD Deliverables against Benchmark Task via MCP...")
    eval_res = json.loads(
        evaluate_workspace_deliverables(
            target_workspace_dir=str(deploy_dir),
            task_id="tdd-user-story-implementation",
        )
    )
    print(f"-> Evaluation Completed! Overall Composite Score: {eval_res.get('overall_composite_score', 'N/A')}/100")
    print(f"-> Deterministic Verifiers Score: {eval_res.get('deterministic_score', 'N/A')}%")
    for v in eval_res.get("verifiers", []):
        badge = "PASS" if v["passed"] else "FAIL"
        print(f"   [{badge}] {v['name']}")

    print("\n[SUCCESS] Demo 2 completed cleanly!")


if __name__ == "__main__":
    run_demo()
