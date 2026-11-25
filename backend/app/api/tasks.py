"""API endpoints for Benchmark Tasks & Verifier Specs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.storage import delete_task, get_task, list_tasks, save_task, yaml_to_task
from app.schemas.task import TaskSpec


router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskWithYamlResponse(BaseModel):
    task: TaskSpec
    raw_yaml: str
    file_path: str


class SaveTaskRequest(BaseModel):
    task: Optional[TaskSpec] = None
    raw_yaml: Optional[str] = None
    previous_id: Optional[str] = None


@router.get("", response_model=List[TaskSpec])
def api_list_tasks() -> List[TaskSpec]:
    return list_tasks()


@router.get("/{task_id}", response_model=TaskWithYamlResponse)
def api_get_task(task_id: str) -> TaskWithYamlResponse:
    found = get_task(task_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    task, raw, path = found
    return TaskWithYamlResponse(task=task, raw_yaml=raw, file_path=str(path))


@router.post("", response_model=TaskWithYamlResponse)
def api_save_task(req: SaveTaskRequest) -> TaskWithYamlResponse:
    try:
        if req.raw_yaml:
            parsed = yaml_to_task(req.raw_yaml)
            t, raw, path = save_task(parsed, raw_yaml_override=req.raw_yaml)
        elif req.task:
            t, raw, path = save_task(req.task)
        else:
            raise ValueError("Provide either task or raw_yaml")
        if req.previous_id and req.previous_id != t.id:
            delete_task(req.previous_id)
        return TaskWithYamlResponse(task=t, raw_yaml=raw, file_path=str(path))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid task specification: {exc}") from exc


@router.delete("/{task_id}")
def api_delete_task(task_id: str) -> Dict[str, Any]:
    if not delete_task(task_id):
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return {"deleted": True, "id": task_id}
