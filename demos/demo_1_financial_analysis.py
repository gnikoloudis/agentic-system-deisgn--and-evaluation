"""Demo 1: Financial Market & News Correlation via HarnessForge MCP Tools.

Demonstrates:
1. Discovering available MCP presets (sqlite, yahoofinance).
2. Calling `describe_and_build_system` to design the multi-agent financial intelligence team.
3. Saving and compiling the architecture for Antigravity & Claude Code with native MCP configurations.
4. Creating the benchmark task with deterministic pytest assertions.
5. Evaluating deliverables and obtaining 4-layer scorecard results.
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
    get_advisor_recommendations,
    list_mcp_catalog,
    validate_and_save_blueprint,
)


def run_demo():
    print("=" * 80)
    print("DEMO 1: Financial Analysis & News Correlation with SQLite & YahooFinance MCP")
    print("=" * 80)

    # 1. Inspect MCP catalog
    print("\n[Step 1] Querying MCP Catalog for Financial Tools...")
    catalog = json.loads(list_mcp_catalog())
    available = [s["id"] for s in catalog["mcp_servers"]]
    print(f"-> Available MCP Servers: {', '.join(available)}")
    assert "sqlite" in available and "yahoofinance" in available

    # 2. Describe and build the system
    print("\n[Step 2] Describing & Building Agent System via MCP...")
    build_raw = describe_and_build_system(
        description="Financial market correlation team using sqlite and yahoofinance MCPs to analyze historical stock prices and news events.",
        target_harness="antigravity",
        topology_pattern="generator-verifier-loop",
        mcp_servers="sqlite, yahoofinance",
        system_id="financial-market-news-analyst",
        system_name="Financial Market & News Correlation Analyst Team",
    )
    build_res = json.loads(build_raw)
    print(f"-> Blueprint Generated: {build_res['blueprint_id']} ({build_res['name']})")
    print(f"-> Assigned Subagents: {', '.join(build_res['subagents'])}")
    print(f"-> Assigned MCPs: {', '.join(build_res['mcp_servers'])}")

    # 3. Validate and save
    print("\n[Step 3] Validating and Persisting Blueprint YAML...")
    save_res = json.loads(validate_and_save_blueprint(build_res["yaml"]))
    print(f"-> Saved Blueprint to: {save_res['file_path']}")

    # 4. Compile and deploy
    deploy_dir = Path(__file__).resolve().parent.parent / ".harness-workspaces" / "demo1_financial_workspace"
    deploy_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[Step 4] Compiling and Deploying to Workspace: {deploy_dir}...")
    deploy_res = json.loads(
        compile_and_deploy_system(
            blueprint_id="financial-market-news-analyst",
            harness="antigravity",
            target_workspace_dir=str(deploy_dir),
        )
    )
    print(f"-> Deployed {deploy_res['files_count']} Native Config Files:")
    for f in deploy_res["deployed_files"][:6]:
        print(f"   • {f}")

    # 5. Create Benchmark Task
    print("\n[Step 5] Authoring Financial Benchmark Task with Verifiers via MCP...")
    verifiers = [
        {
            "id": "check_correlation_report_exists",
            "name": "Correlation Report Output Exists",
            "type": "file_exists",
            "target_path": "correlation_report.json",
            "weight": 2.0,
            "required": True,
        },
        {
            "id": "check_report_has_ticker_data",
            "name": "Report Contains Valid Ticker Metrics",
            "type": "file_contains_regex",
            "target_path": "correlation_report.json",
            "pattern": '"(AAPL|NVDA)"',
            "weight": 2.0,
            "required": True,
        },
    ]
    task_res = json.loads(
        create_benchmark_task(
            task_id="financial-news-correlation-benchmark",
            name="Financial News Correlation & Anomaly Ingestion Benchmark",
            description="Evaluates correlation between price series and news events via sqlite & yahoofinance.",
            prompt="Ingest historical prices for AAPL and NVDA from SQLite and correlate with news events.",
            verifiers_json=json.dumps(verifiers),
            workspace_source="tasks/sample_repos/financial_analysis",
        )
    )
    print(f"-> Task Created: {task_res['task_id']} ({task_res['name']}) with {task_res['verifiers_count']} verifiers.")

    # 6. Simulate generated deliverable in workspace and evaluate
    print("\n[Step 6] Simulating Generated Deliverables & Evaluating Workspace via MCP...")
    mock_report = {
        "tickers": ["AAPL", "NVDA"],
        "analysis_summary": "Strong positive correlation (r=0.82) observed between positive product announcements and next-day price momentum.",
        "findings": [
            {"date": "2024-01-12", "ticker": "AAPL", "return": 0.037, "headline": "Record developer enthusiasm reported for VisionOS"},
            {"date": "2024-01-11", "ticker": "NVDA", "return": 0.046, "headline": "Analysts raise Nvidia quarterly targets by 20%"}
        ]
    }
    (deploy_dir / "correlation_report.json").write_text(json.dumps(mock_report, indent=2), encoding="utf-8")

    eval_res = json.loads(
        evaluate_workspace_deliverables(
            target_workspace_dir=str(deploy_dir),
            task_id="financial-news-correlation-benchmark",
        )
    )
    print(f"-> Evaluation Completed! Overall Composite Score: {eval_res.get('overall_composite_score', 'N/A')}/100")
    print(f"-> Deterministic Verifiers Score: {eval_res.get('deterministic_score', 'N/A')}%")
    for v in eval_res.get("verifiers", []):
        badge = "PASS" if v["passed"] else "FAIL"
        print(f"   [{badge}] {v['name']}")

    print("\n[SUCCESS] Demo 1 completed cleanly!")


if __name__ == "__main__":
    run_demo()
