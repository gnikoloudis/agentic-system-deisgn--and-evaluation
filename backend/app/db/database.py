"""SQLite persistence layer for Runs, Telemetry Events, Evaluations, and Advisor Suggestions."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from app.config import DB_PATH, ensure_directories
from app.schemas.evaluation import (
    AdvisorSuggestion,
    EvaluationReport,
    RunRecordSchema,
    TelemetryEvent,
)

_db_lock = threading.RLock()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    ensure_directories()
    target_path = db_path or DB_PATH
    with _db_lock:
        conn = sqlite3.connect(str(target_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db(db_path: Optional[Path] = None) -> None:
    """Create SQLite tables if they do not already exist."""
    with get_conn(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                architecture_id TEXT NOT NULL,
                architecture_name TEXT NOT NULL,
                architecture_version TEXT NOT NULL,
                task_id TEXT NOT NULL,
                task_name TEXT NOT NULL,
                harness TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                sandbox_path TEXT NOT NULL,
                cli_command TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                git_diff TEXT DEFAULT '',
                changed_files_json TEXT DEFAULT '[]',
                evaluation_json TEXT,
                blueprint_snapshot_json TEXT,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS telemetry_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                event_type TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                tool_name TEXT,
                tool_input_json TEXT,
                tool_output TEXT,
                status TEXT NOT NULL,
                duration_ms REAL DEFAULT 0.0,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_read_tokens INTEGER DEFAULT 0,
                cache_write_tokens INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                message TEXT,
                metadata_json TEXT DEFAULT '{}',
                FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_telemetry_run_id ON telemetry_events(run_id);

            CREATE TABLE IF NOT EXISTS advisor_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                architecture_id TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
            );
            """
        )


def save_run(run: RunRecordSchema, blueprint_snapshot: Optional[Dict[str, Any]] = None) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO runs (
                id, architecture_id, architecture_name, architecture_version,
                task_id, task_name, harness, mode, status, sandbox_path,
                cli_command, started_at, completed_at, git_diff,
                changed_files_json, evaluation_json, blueprint_snapshot_json, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.id,
                run.architecture_id,
                run.architecture_name,
                run.architecture_version,
                run.task_id,
                run.task_name,
                run.harness,
                run.mode,
                run.status,
                run.sandbox_path,
                run.cli_command,
                run.started_at,
                run.completed_at,
                run.git_diff,
                json.dumps(run.changed_files),
                run.evaluation.model_dump_json() if run.evaluation else None,
                json.dumps(blueprint_snapshot) if blueprint_snapshot else None,
                run.error_message,
            ),
        )


def update_run_status(
    run_id: str,
    status: str,
    completed_at: Optional[str] = None,
    git_diff: Optional[str] = None,
    changed_files: Optional[List[str]] = None,
    evaluation: Optional[EvaluationReport] = None,
    error_message: Optional[str] = None,
) -> Optional[RunRecordSchema]:
    run = get_run(run_id)
    if not run:
        return None
    run.status = status  # type: ignore[assignment]
    if completed_at is not None:
        run.completed_at = completed_at
    if git_diff is not None:
        run.git_diff = git_diff
    if changed_files is not None:
        run.changed_files = changed_files
    if evaluation is not None:
        run.evaluation = evaluation
    if error_message is not None:
        run.error_message = error_message
    save_run(run)
    return run


def _row_to_run(row: sqlite3.Row) -> RunRecordSchema:
    eval_data = json.loads(row["evaluation_json"]) if row["evaluation_json"] else None
    return RunRecordSchema(
        id=row["id"],
        architecture_id=row["architecture_id"],
        architecture_name=row["architecture_name"],
        architecture_version=row["architecture_version"],
        task_id=row["task_id"],
        task_name=row["task_name"],
        harness=row["harness"],
        mode=row["mode"],
        status=row["status"],
        sandbox_path=row["sandbox_path"],
        cli_command=row["cli_command"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        git_diff=row["git_diff"] or "",
        changed_files=json.loads(row["changed_files_json"] or "[]"),
        evaluation=EvaluationReport.model_validate(eval_data) if eval_data else None,
        error_message=row["error_message"],
    )


def get_run(run_id: str) -> Optional[RunRecordSchema]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return _row_to_run(row) if row else None


def list_runs(
    architecture_id: Optional[str] = None,
    task_id: Optional[str] = None,
    harness: Optional[str] = None,
    limit: int = 100,
) -> List[RunRecordSchema]:
    query = "SELECT * FROM runs WHERE 1=1"
    params: List[Any] = []
    if architecture_id:
        query += " AND architecture_id = ?"
        params.append(architecture_id)
    if task_id:
        query += " AND task_id = ?"
        params.append(task_id)
    if harness:
        query += " AND harness = ?"
        params.append(harness)
    query += " ORDER BY COALESCE(completed_at, started_at) DESC, started_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
        return [_row_to_run(r) for r in rows]


def list_runs_by_statuses(statuses: List[str], limit: int = 100) -> List[RunRecordSchema]:
    if not statuses:
        return []
    placeholders = ",".join("?" for _ in statuses)
    query = f"SELECT * FROM runs WHERE status IN ({placeholders}) ORDER BY started_at DESC LIMIT ?"
    params: List[Any] = [*statuses, limit]
    with get_conn() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
        return [_row_to_run(r) for r in rows]


def delete_run(run_id: str) -> bool:
    with get_conn() as conn:
        conn.execute("DELETE FROM telemetry_events WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM advisor_suggestions WHERE run_id = ?", (run_id,))
        cur = conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        return cur.rowcount > 0


def delete_all_runs() -> int:
    """Delete all runs, telemetry events, and advisor suggestions from SQLite."""
    with get_conn() as conn:
        conn.execute("DELETE FROM telemetry_events")
        conn.execute("DELETE FROM advisor_suggestions")
        cur = conn.execute("DELETE FROM runs")
        return cur.rowcount


def cleanup_orphaned_running_runs() -> int:
    """Mark any runs left in 'running' state after a server reload/restart as 'cancelled'."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE runs
            SET status = 'cancelled',
                completed_at = ?,
                error_message = 'Run interrupted by server reload or restart.'
            WHERE status IN ('running', 'preparing_sandbox', 'evaluating')
            """,
            (utc_now_iso(),),
        )
        return cur.rowcount


def append_telemetry_event(event: TelemetryEvent) -> TelemetryEvent:
    with get_conn() as conn:
        step_idx = event.metadata.get("step_index") if isinstance(event.metadata, dict) else None

        # Coalesce streaming AssistantMessage text_delta chunks belonging to the same step_index
        if event.event_type == "AssistantMessage" and step_idx is not None:
            existing = conn.execute(
                """
                SELECT id, message, metadata_json, input_tokens, output_tokens, cache_read_tokens, duration_ms, cost_usd
                FROM telemetry_events
                WHERE run_id = ? AND event_type = 'AssistantMessage'
                ORDER BY id DESC LIMIT 1
                """,
                (event.run_id,),
            ).fetchone()
            if existing:
                ex_meta = json.loads(existing["metadata_json"] or "{}")
                if ex_meta.get("step_index") == step_idx:
                    merged_msg = (existing["message"] or "") + (event.message or "")
                    in_tok = max(int(existing["input_tokens"] or 0), event.input_tokens)
                    out_tok = max(int(existing["output_tokens"] or 0), event.output_tokens)
                    cache_tok = max(int(existing["cache_read_tokens"] or 0), event.cache_read_tokens)
                    dur_ms = max(float(existing["duration_ms"] or 0.0), event.duration_ms)
                    cost = max(float(existing["cost_usd"] or 0.0), event.cost_usd)
                    conn.execute(
                        """
                        UPDATE telemetry_events
                        SET message = ?, input_tokens = ?, output_tokens = ?, cache_read_tokens = ?,
                            duration_ms = ?, cost_usd = ?, timestamp = ?
                        WHERE id = ?
                        """,
                        (
                            merged_msg,
                            in_tok,
                            out_tok,
                            cache_tok,
                            dur_ms,
                            cost,
                            event.timestamp,
                            existing["id"],
                        ),
                    )
                    event.id = existing["id"]
                    event.message = merged_msg
                    event.input_tokens = in_tok
                    event.output_tokens = out_tok
                    event.cache_read_tokens = cache_tok
                    event.duration_ms = dur_ms
                    event.cost_usd = cost
                    return event

        # Deduplicate repeated PreToolUse / SubagentStart state ticks for the same (step_index, tool_name)
        if event.event_type in ("PreToolUse", "SubagentStart") and step_idx is not None:
            existing_tool = conn.execute(
                """
                SELECT id, message, metadata_json, tool_input_json
                FROM telemetry_events
                WHERE run_id = ? AND event_type = ? AND tool_name = ?
                ORDER BY id DESC LIMIT 1
                """,
                (event.run_id, event.event_type, event.tool_name),
            ).fetchone()
            if existing_tool:
                ex_meta = json.loads(existing_tool["metadata_json"] or "{}")
                if ex_meta.get("step_index") == step_idx:
                    new_msg = event.message or existing_tool["message"]
                    new_input = (
                        json.dumps(event.tool_input)
                        if event.tool_input
                        else existing_tool["tool_input_json"]
                    )
                    conn.execute(
                        """
                        UPDATE telemetry_events
                        SET message = ?, tool_input_json = ?, duration_ms = MAX(duration_ms, ?),
                            input_tokens = MAX(input_tokens, ?), output_tokens = MAX(output_tokens, ?),
                            cost_usd = MAX(cost_usd, ?)
                        WHERE id = ?
                        """,
                        (
                            new_msg,
                            new_input,
                            event.duration_ms,
                            event.input_tokens,
                            event.output_tokens,
                            event.cost_usd,
                            existing_tool["id"],
                        ),
                    )
                    event.id = existing_tool["id"]
                    event.message = new_msg
                    return event

        cur = conn.execute(
            """
            INSERT INTO telemetry_events (
                run_id, timestamp, source, event_type, agent_id,
                tool_name, tool_input_json, tool_output, status, duration_ms,
                input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                cost_usd, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.run_id,
                event.timestamp,
                event.source,
                event.event_type,
                event.agent_id,
                event.tool_name,
                json.dumps(event.tool_input) if event.tool_input is not None else None,
                event.tool_output,
                event.status,
                event.duration_ms,
                event.input_tokens,
                event.output_tokens,
                event.cache_read_tokens,
                event.cache_write_tokens,
                event.cost_usd,
                event.message,
                json.dumps(event.metadata),
            ),
        )
        event.id = cur.lastrowid
        return event


def list_telemetry_events(run_id: str) -> List[TelemetryEvent]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM telemetry_events WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
        events: List[TelemetryEvent] = []
        for r in rows:
            events.append(
                TelemetryEvent(
                    id=r["id"],
                    run_id=r["run_id"],
                    timestamp=r["timestamp"],
                    source=r["source"],
                    event_type=r["event_type"],
                    agent_id=r["agent_id"],
                    tool_name=r["tool_name"],
                    tool_input=json.loads(r["tool_input_json"]) if r["tool_input_json"] else None,
                    tool_output=r["tool_output"],
                    status=r["status"],
                    duration_ms=r["duration_ms"] or 0.0,
                    input_tokens=r["input_tokens"] or 0,
                    output_tokens=r["output_tokens"] or 0,
                    cache_read_tokens=r["cache_read_tokens"] or 0,
                    cache_write_tokens=r["cache_write_tokens"] or 0,
                    cost_usd=r["cost_usd"] or 0.0,
                    message=r["message"],
                    metadata=json.loads(r["metadata_json"] or "{}"),
                )
            )
        return events


def save_advisor_suggestion(suggestion: AdvisorSuggestion) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO advisor_suggestions (run_id, architecture_id, generated_at, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                suggestion.run_id,
                suggestion.architecture_id,
                suggestion.generated_at,
                suggestion.model_dump_json(),
            ),
        )


def get_latest_advisor_suggestion(run_id: str) -> Optional[AdvisorSuggestion]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT payload_json FROM advisor_suggestions WHERE run_id = ? ORDER BY id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        if not row:
            return None
        return AdvisorSuggestion.model_validate_json(row["payload_json"])
