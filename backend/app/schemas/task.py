"""Schemas for Benchmark Tasks, Verification Checks, and Task Suites."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class VerificationCheck(BaseModel):
    """A deterministic verification check executed after an agent completes a task."""

    id: str = Field(..., description="Unique check ID (e.g. 'unit_tests', 'lint_check', 'diff_assertion')")
    name: str = Field(..., description="Human-readable check name")
    type: Literal[
        "command_exit_code",
        "pytest_pass",
        "file_exists",
        "file_contains_regex",
        "file_not_contains_regex",
        "git_diff_contains",
        "git_diff_max_lines",
        "user_story_invest_check",
        "markdown_sections_present",
        "mermaid_diagram_valid",
    ] = Field(default="command_exit_code")
    command: Optional[str] = Field(
        default=None,
        description="Shell command to run inside the sandbox when type is command_exit_code or pytest_pass",
    )
    target_path: Optional[str] = Field(
        default=None,
        description="Relative file path inside sandbox for file assertions",
    )
    pattern: Optional[str] = Field(
        default=None,
        description="Regex pattern or substring for file/diff assertions",
    )
    max_lines: Optional[int] = Field(
        default=None,
        description="Max changed lines for git_diff_max_lines check",
    )
    weight: float = Field(default=1.0, ge=0.0, description="Scoring weight of this check")
    required: bool = Field(default=True, description="Whether task pass/fail depends on this check")
    timeout_seconds: int = Field(default=60, ge=5)


class RubricDimension(BaseModel):
    """A grading dimension for LLM-as-a-Judge and Human review."""

    id: str
    name: str
    description: str
    weight: float = Field(default=1.0, ge=0.1)


class TaskSpec(BaseModel):
    """Specification for an executable evaluation task."""

    api_version: str = Field(default="harnessforge/v1")
    kind: Literal["TaskSpec"] = Field(default="TaskSpec")
    id: str = Field(..., description="Unique task slug")
    name: str = Field(..., description="Display title of the task")
    category: Literal[
        "bugfix",
        "feature",
        "refactor",
        "security",
        "test-writing",
        "frontend-ui",
        "business-analysis",
        "product-management",
        "consulting",
        "custom",
    ] = Field(default="bugfix")
    difficulty: Literal["easy", "medium", "hard"] = Field(default="medium")
    description: str = Field(default="", description="Overview of what this benchmark tests")
    prompt: str = Field(..., description="Exact task prompt sent to the harness")
    workspace_source: str = Field(
        default="tasks/sample_repos/auth_service",
        description="Relative path to starter repo, absolute local git path, or git URL",
    )
    base_commit: Optional[str] = Field(
        default=None,
        description="Optional git commit/branch to checkout when creating worktree",
    )
    expected_subagents: List[str] = Field(
        default_factory=list,
        description="Optional list of subagent IDs expected to participate",
    )
    verifiers: List[VerificationCheck] = Field(default_factory=list)
    rubric: List[RubricDimension] = Field(
        default_factory=lambda: [
            RubricDimension(
                id="correctness",
                name="Task Correctness & Completeness",
                description="Did the solution completely solve the prompt without breaking existing behavior?",
                weight=1.5,
            ),
            RubricDimension(
                id="code_quality",
                name="Code Quality & Minimal Blast Radius",
                description="Is the code idiomatic, clean, well-tested, and focused without extraneous edits?",
                weight=1.0,
            ),
            RubricDimension(
                id="orchestration_fidelity",
                name="Agentic Architecture & Handoff Quality",
                description="Did the orchestrator and subagents follow their designated roles and handoff rules cleanly?",
                weight=1.2,
            ),
        ]
    )
    tags: List[str] = Field(default_factory=list)
    env_vars: Dict[str, str] = Field(default_factory=dict)
