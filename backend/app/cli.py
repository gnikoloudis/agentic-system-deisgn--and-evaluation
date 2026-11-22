"""Typer CLI for HarnessForge (`harnessforge serve | list | compile | export | run | compare`)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional
import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from app.compilers import compile_architecture, deploy_compiled_files
from app.config import settings
from app.db.database import init_db
from app.db.storage import get_blueprint, list_blueprints, list_tasks
from app.evaluator.advisor import (
    compare_runs_ab,
    evaluate_completed_run,
    generate_advisor_suggestion,
)
from app.runner.executor import start_execution_run
from app.schemas.blueprint import HarnessType
from app.schemas.evaluation import RunMode

app = typer.Typer(
    name="harnessforge",
    help="HarnessForge — Multi-Harness Agent Architecture Design & Evaluation CLI (Claude Code, Antigravity, OpenCode)",
)
console = Console()


@app.command("serve")
def cmd_serve(
    host: str = typer.Option(settings.host, "--host", "-h", help="Host interface to bind"),
    port: int = typer.Option(settings.port, "--port", "-p", help="Port for backend API server"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
) -> None:
    """Start the HarnessForge FastAPI backend server."""
    init_db()
    console.print(f"[bold cyan]Starting HarnessForge API Server on http://{host}:{port}[/bold cyan]")
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


@app.command("list")
def cmd_list() -> None:
    """List available architecture blueprints and benchmark tasks."""
    init_db()
    bps = list_blueprints()
    bp_table = Table(title="Architecture Blueprints (blueprints/*.yaml)")
    bp_table.add_column("ID", style="cyan", no_wrap=True)
    bp_table.add_column("Name", style="bold")
    bp_table.add_column("Version")
    bp_table.add_column("Topology Pattern", style="magenta")
    bp_table.add_column("Subagents", justify="right")
    for bp in bps:
        bp_table.add_row(
            bp.metadata.id,
            bp.metadata.name,
            bp.metadata.version,
            bp.topology.pattern,
            str(len(bp.subagents)),
        )
    console.print(bp_table)

    tasks = list_tasks()
    t_table = Table(title="Benchmark Tasks (tasks/*.yaml)")
    t_table.add_column("ID", style="green", no_wrap=True)
    t_table.add_column("Name", style="bold")
    t_table.add_column("Category")
    t_table.add_column("Difficulty")
    t_table.add_column("Verifiers", justify="right")
    for t in tasks:
        t_table.add_row(t.id, t.name, t.category, t.difficulty, str(len(t.verifiers)))
    console.print(t_table)


@app.command("compile")
def cmd_compile(
    architecture_id: str = typer.Argument(..., help="Blueprint ID (e.g. planner-coder-verifier)"),
    harness: str = typer.Option("claude_code", "--harness", "-t", help="claude_code | antigravity | opencode"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o", help="Optional target directory to deploy files"),
) -> None:
    """Compile an architecture blueprint to native harness files (Claude Code, Antigravity, or OpenCode)."""
    found = get_blueprint(architecture_id)
    if not found:
        console.print(f"[red]Blueprint '{architecture_id}' not found.[/red]")
        raise typer.Exit(code=1)
    bp, _, _ = found
    res = compile_architecture(bp, harness=harness)  # type: ignore[arg-type]

    table = Table(title=f"Compiled `{bp.metadata.name}` for `{harness}`")
    table.add_column("Relative File Path", style="cyan")
    table.add_column("Description")
    table.add_column("Size (chars)", justify="right")
    for f in res.files:
        table.add_row(f.relative_path, f.description, str(len(f.content)))
    console.print(table)
    console.print(f"[bold]Headless CLI Preview:[/bold] `{res.cli_preview_command}`")

    if output_dir:
        dest = Path(output_dir).resolve()
        deploy_compiled_files(res, dest)
        console.print(f"[bold green]Deployed {len(res.files)} files to {dest}[/bold green]")


@app.command("run")
def cmd_run(
    architecture_id: str = typer.Argument(..., help="Architecture blueprint ID"),
    task_id: str = typer.Argument(..., help="Benchmark task ID"),
    harness: str = typer.Option("claude_code", "--harness", "-t", help="claude_code | antigravity | opencode"),
    mode: str = typer.Option("simulated_benchmark", "--mode", "-m", help="headless | interactive | simulated_benchmark"),
    advisor: bool = typer.Option(True, "--advisor/--no-advisor", help="Generate AI Architecture Advisor v2 diff"),
) -> None:
    """Execute a benchmark task in an isolated Git sandbox and run the 4-layer evaluation engine."""
    init_db()

    async def _run_and_eval():
        async def _eval_cb(rid: str):
            await asyncio.to_thread(evaluate_completed_run, rid)

        run_rec = await start_execution_run(
            architecture_id=architecture_id,
            task_id=task_id,
            harness=harness,  # type: ignore[arg-type]
            mode=mode,  # type: ignore[arg-type]
            auto_evaluate_callback=_eval_cb,
        )
        # Wait for background task if headless/simulated
        from app.runner.executor import _active_tasks

        bg = _active_tasks.get(run_rec.id)
        if bg:
            await bg
        return run_rec.id

    run_id = asyncio.run(_run_and_eval())
    report = evaluate_completed_run(run_id)

    console.print(f"\n[bold green]Evaluation Complete for Run `{run_id}`[/bold green]")
    console.print(
        f"Composite Score: [bold cyan]{report.overall_composite_score:.1f}/100[/bold cyan] | "
        f"Deterministic: {report.deterministic_score:.1f}% | "
        f"Topology Adherence: {report.topology_adherence_pct:.1f}% | "
        f"Efficiency: {report.efficiency_pct:.1f}% | "
        f"Judge: {report.judge_score:.1f}/100"
    )

    if advisor:
        sug = generate_advisor_suggestion(run_id)
        console.print(f"\n[bold yellow]AI Architecture Advisor ({sug.proposed_version}):[/bold yellow] {sug.summary}")
        for chg in sug.changes_made:
            console.print(f"  • {chg}")


@app.command("evaluate-dir")
def cmd_evaluate_dir(
    project_dir: str = typer.Argument(..., help="Path to deployed project directory (e.g. test_application_docs)"),
    task_id: Optional[str] = typer.Option(None, "--task", "-k", help="Optional benchmark task ID for verifier checks"),
) -> None:
    """Evaluate a deployed project directory using its .harness-eval telemetry & deliverables, and run the AI Advisor."""
    init_db()
    from app.api.runs import EvaluateDirectoryRequest, api_evaluate_deployed_directory

    req = EvaluateDirectoryRequest(project_directory=project_dir, task_id=task_id)
    run_rec = asyncio.run(api_evaluate_deployed_directory(req))
    report = run_rec.evaluation
    assert report is not None

    console.print(f"\n[bold green]Evaluated Deployed Project `{run_rec.sandbox_path}` (Run `{run_rec.id}`)[/bold green]")
    console.print(
        f"Composite Score: [bold cyan]{report.overall_composite_score:.1f}/100[/bold cyan] | "
        f"Deterministic Verifiers: {report.deterministic_score:.1f}% | "
        f"Topology Adherence: {report.topology_adherence_pct:.1f}% | "
        f"Efficiency: {report.efficiency_pct:.1f}% | "
        f"Judge: {report.judge_score:.1f}/100"
    )
    for vr in report.verifier_results:
        badge = "[green]PASS[/green]" if vr.passed else "[red]FAIL[/red]"
        console.print(f"  {badge} {vr.name}: {vr.output.splitlines()[0] if vr.output else ''}")

    sug = generate_advisor_suggestion(run_rec.id)
    console.print(f"\n[bold yellow]AI Architecture Advisor Project Improvements (v{sug.proposed_version}):[/bold yellow]")
    for d in sug.diagnoses:
        console.print(f"  • [{d.severity.upper()}] {d.target_component}: {d.finding}")
        console.print(f"    [cyan]-> Recommendation:[/cyan] {d.recommendation}")


if __name__ == "__main__":
    app()
