"""API endpoints for Multi-Layer Evaluation, Human Rating, Side-by-Side A/B Comparison, and AI Architecture Advisor."""

from __future__ import annotations

import asyncio
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import JudgeProviderConfig, settings
from app.db.database import (
    get_latest_advisor_suggestion,
    get_run,
    save_run,
)
from app.db.storage import save_blueprint
from app.evaluator.advisor import (
    compare_runs_ab,
    evaluate_completed_run,
    generate_advisor_suggestion,
)
from app.runner.executor import _active_tasks
from app.schemas.blueprint import AgentArchitecture
from app.schemas.evaluation import (
    ABComparisonResponse,
    AdvisorSuggestion,
    EvaluationReport,
    HumanGradeRequest,
)


router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


class CompareRunsRequest(BaseModel):
    run_ids: List[str]


class ApplyAdvisorPatchRequest(BaseModel):
    save_as_new_id: str | None = None


@router.post("/runs/{run_id}/evaluate", response_model=EvaluationReport)
async def api_trigger_evaluation(run_id: str) -> EvaluationReport:
    try:
        bg_task = _active_tasks.get(run_id)
        if bg_task and not bg_task.done():
            await bg_task
        return await asyncio.to_thread(evaluate_completed_run, run_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs/{run_id}/human-grade", response_model=EvaluationReport)
def api_save_human_grade(run_id: str, req: HumanGradeRequest) -> EvaluationReport:
    run = get_run(run_id)
    if not run or not run.evaluation:
        raise HTTPException(status_code=404, detail=f"Evaluated run '{run_id}' not found")
    run.evaluation.judge.human_rating = req.rating
    run.evaluation.judge.human_notes = req.notes
    save_run(run)
    return run.evaluation


@router.post("/compare", response_model=ABComparisonResponse)
async def api_compare_runs(req: CompareRunsRequest) -> ABComparisonResponse:
    if not req.run_ids:
        raise HTTPException(status_code=400, detail="Provide at least one run_id to compare")
    return await asyncio.to_thread(compare_runs_ab, req.run_ids)


@router.get("/runs/{run_id}/advisor", response_model=AdvisorSuggestion)
async def api_get_or_generate_advisor(run_id: str, regenerate: bool = False) -> AdvisorSuggestion:
    if not regenerate:
        existing = get_latest_advisor_suggestion(run_id)
        if existing:
            return existing
    try:
        return await asyncio.to_thread(generate_advisor_suggestion, run_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs/{run_id}/advisor/apply", response_model=AgentArchitecture)
async def api_apply_advisor_suggestion(run_id: str, req: ApplyAdvisorPatchRequest) -> AgentArchitecture:
    """Apply the AI Architecture Advisor's proposed v2 YAML blueprint patch directly to disk."""
    suggestion = get_latest_advisor_suggestion(run_id)
    if not suggestion:
        suggestion = await asyncio.to_thread(generate_advisor_suggestion, run_id)

    proposed = suggestion.proposed_blueprint
    if req.save_as_new_id:
        proposed.metadata.id = req.save_as_new_id
        proposed.metadata.name = f"{proposed.metadata.name} ({req.save_as_new_id})"

    saved_bp, _, _ = save_blueprint(proposed)
    return saved_bp


@router.get("/settings/judge", response_model=JudgeProviderConfig)
def api_get_judge_settings() -> JudgeProviderConfig:
    return settings.judge


@router.put("/settings/judge", response_model=JudgeProviderConfig)
def api_update_judge_settings(cfg: JudgeProviderConfig) -> JudgeProviderConfig:
    settings.judge = cfg
    return settings.judge
