"""Disk YAML storage manager for Architecture Blueprints and Task Specs."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple
import yaml

from app.config import BLUEPRINTS_DIR, TASKS_DIR, ensure_directories
from app.schemas.blueprint import AgentArchitecture
from app.schemas.task import TaskSpec


def blueprint_to_yaml(blueprint: AgentArchitecture) -> str:
    data = blueprint.model_dump(mode="json")
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)


def yaml_to_blueprint(raw_yaml: str) -> AgentArchitecture:
    data = yaml.safe_load(raw_yaml)
    return AgentArchitecture.model_validate(data)


def list_blueprints() -> List[AgentArchitecture]:
    ensure_directories()
    blueprints: List[AgentArchitecture] = []
    for path in sorted(BLUEPRINTS_DIR.glob("*.yaml")):
        try:
            raw = path.read_text(encoding="utf-8")
            blueprints.append(yaml_to_blueprint(raw))
        except Exception as exc:
            print(f"[WARN] Failed to load blueprint {path}: {exc}")
    return blueprints


def get_blueprint(architecture_id: str) -> Optional[Tuple[AgentArchitecture, str, Path]]:
    ensure_directories()
    direct_path = BLUEPRINTS_DIR / f"{architecture_id}.yaml"
    if direct_path.exists():
        raw = direct_path.read_text(encoding="utf-8")
        return yaml_to_blueprint(raw), raw, direct_path
    for path in sorted(BLUEPRINTS_DIR.glob("*.yaml")):
        try:
            raw = path.read_text(encoding="utf-8")
            bp = yaml_to_blueprint(raw)
            if bp.metadata.id == architecture_id:
                return bp, raw, path
        except Exception:
            continue
    return None


def save_blueprint(blueprint: AgentArchitecture, raw_yaml_override: Optional[str] = None) -> Tuple[AgentArchitecture, str, Path]:
    ensure_directories()
    if raw_yaml_override is not None:
        blueprint = yaml_to_blueprint(raw_yaml_override)
        yaml_str = raw_yaml_override
    else:
        yaml_str = blueprint_to_yaml(blueprint)
    target_path = BLUEPRINTS_DIR / f"{blueprint.metadata.id}.yaml"
    target_path.write_text(yaml_str, encoding="utf-8")
    return blueprint, yaml_str, target_path


def delete_blueprint(architecture_id: str) -> bool:
    found = get_blueprint(architecture_id)
    if not found:
        return False
    _, _, path = found
    path.unlink(missing_ok=True)
    return True


def task_to_yaml(task: TaskSpec) -> str:
    data = task.model_dump(mode="json")
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)


def yaml_to_task(raw_yaml: str) -> TaskSpec:
    data = yaml.safe_load(raw_yaml)
    return TaskSpec.model_validate(data)


def list_tasks() -> List[TaskSpec]:
    ensure_directories()
    tasks: List[TaskSpec] = []
    for path in sorted(TASKS_DIR.glob("*.yaml")):
        try:
            raw = path.read_text(encoding="utf-8")
            tasks.append(yaml_to_task(raw))
        except Exception as exc:
            print(f"[WARN] Failed to load task {path}: {exc}")
    return tasks


def get_task(task_id: str) -> Optional[Tuple[TaskSpec, str, Path]]:
    ensure_directories()
    direct_path = TASKS_DIR / f"{task_id}.yaml"
    if direct_path.exists():
        raw = direct_path.read_text(encoding="utf-8")
        return yaml_to_task(raw), raw, direct_path
    for path in sorted(TASKS_DIR.glob("*.yaml")):
        try:
            raw = path.read_text(encoding="utf-8")
            t = yaml_to_task(raw)
            if t.id == task_id:
                return t, raw, path
        except Exception:
            continue
    return None


def save_task(task: TaskSpec, raw_yaml_override: Optional[str] = None) -> Tuple[TaskSpec, str, Path]:
    ensure_directories()
    if raw_yaml_override is not None:
        task = yaml_to_task(raw_yaml_override)
        yaml_str = raw_yaml_override
    else:
        yaml_str = task_to_yaml(task)
    target_path = TASKS_DIR / f"{task.id}.yaml"
    target_path.write_text(yaml_str, encoding="utf-8")
    return task, yaml_str, target_path


def delete_task(task_id: str) -> bool:
    found = get_task(task_id)
    if not found:
        return False
    _, _, path = found
    path.unlink(missing_ok=True)
    return True
