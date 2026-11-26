"""Layer 1: Deterministic Outcome Graders (Pytest, Shell Commands, File & Git Diff Assertions)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.schemas.evaluation import VerifierCheckResult
from app.schemas.task import VerificationCheck


def find_project_python(project_dir: Path) -> Optional[Path]:
    """Locate a project-local Python virtual environment interpreter if present."""
    candidates = [
        project_dir / ".venv" / "Scripts" / "python.exe",
        project_dir / "venv" / "Scripts" / "python.exe",
        project_dir / "backend" / ".venv" / "Scripts" / "python.exe",
        project_dir / "backend" / "venv" / "Scripts" / "python.exe",
        project_dir / ".venv" / "bin" / "python",
        project_dir / "venv" / "bin" / "python",
        project_dir / "backend" / ".venv" / "bin" / "python",
        project_dir / "backend" / "venv" / "bin" / "python",
    ]
    for cand in candidates:
        if cand.exists() and cand.is_file():
            return cand.resolve()
    return None


def build_project_env(python_exe: Optional[Path]) -> Dict[str, str]:
    """Build subprocess environment with project virtualenv Scripts/bin prepended to PATH."""
    env = os.environ.copy()
    if not python_exe:
        return env
    scripts_dir = str(python_exe.parent)
    env["PATH"] = scripts_dir + os.pathsep + env.get("PATH", "")
    if python_exe.parent.name.lower() in ("scripts", "bin"):
        env["VIRTUAL_ENV"] = str(python_exe.parent.parent)
    return env


def bootstrap_project_python_env(project_dir: Path) -> Tuple[Optional[Path], str]:
    """Automatically create and/or install dependencies into a project's local .venv when pyproject.toml or requirements.txt exists."""
    py_root: Optional[Path] = None
    for cand_root in (project_dir, project_dir / "backend"):
        if (cand_root / "pyproject.toml").exists() or (cand_root / "requirements.txt").exists():
            py_root = cand_root
            break
    if not py_root:
        return find_project_python(project_dir), "No pyproject.toml or requirements.txt found for auto-setup."

    venv_dir = py_root / ".venv"
    venv_py = (
        venv_dir / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else venv_dir / "bin" / "python"
    )
    notes: List[str] = []

    try:
        if not venv_py.exists():
            uv_bin = shutil.which("uv")
            if uv_bin:
                subprocess.run([uv_bin, "venv", str(venv_dir)], cwd=str(py_root), capture_output=True, text=True, timeout=60)
            else:
                subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], cwd=str(py_root), capture_output=True, text=True, timeout=90)
            if venv_py.exists():
                notes.append(f"Created virtual environment at {venv_dir.name}")

        if not venv_py.exists():
            return None, "Failed to create project .venv."

        uv_bin = shutil.which("uv")
        env = build_project_env(venv_py)

        if (py_root / "pyproject.toml").exists():
            if uv_bin:
                res = subprocess.run(
                    [uv_bin, "pip", "install", "--python", str(venv_py), "-e", ".[dev]"],
                    cwd=str(py_root),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                if res.returncode != 0:
                    subprocess.run(
                        [uv_bin, "pip", "install", "--python", str(venv_py), "-e", ".", "pytest"],
                        cwd=str(py_root),
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=180,
                    )
            else:
                res = subprocess.run(
                    [str(venv_py), "-m", "pip", "install", "-q", "-e", ".[dev]"],
                    cwd=str(py_root),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                if res.returncode != 0:
                    subprocess.run(
                        [str(venv_py), "-m", "pip", "install", "-q", "-e", ".", "pytest"],
                        cwd=str(py_root),
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=180,
                    )
            notes.append("Installed dependencies from pyproject.toml")
        elif (py_root / "requirements.txt").exists():
            if uv_bin:
                subprocess.run(
                    [uv_bin, "pip", "install", "--python", str(venv_py), "-r", "requirements.txt", "pytest"],
                    cwd=str(py_root),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
            else:
                subprocess.run(
                    [str(venv_py), "-m", "pip", "install", "-q", "-r", "requirements.txt", "pytest"],
                    cwd=str(py_root),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
            notes.append("Installed dependencies from requirements.txt")

        return venv_py.resolve(), "; ".join(notes) or "Synced project .venv"
    except Exception as exc:
        return find_project_python(project_dir), f"Auto-setup warning: {exc}"


def synthesize_project_verifiers(project_dir: Path) -> List[VerificationCheck]:
    """Automatically synthesize relevant deterministic verifiers for any deployed project folder."""
    verifiers: List[VerificationCheck] = []

    # 1. Python test suite (root tests/, backend/tests/, or test_*.py files)
    has_root_tests = (project_dir / "tests").is_dir() or any(project_dir.glob("test_*.py"))
    has_backend_tests = (project_dir / "backend" / "tests").is_dir()
    if has_root_tests:
        verifiers.append(
            VerificationCheck(
                id="auto_pytest_suite",
                name="Project Pytest Suite (auto-detected)",
                type="pytest_pass",
                command="pytest -v",
                weight=3.0,
                required=True,
                timeout_seconds=120,
            )
        )
    elif has_backend_tests:
        verifiers.append(
            VerificationCheck(
                id="auto_backend_pytest_suite",
                name="Backend Pytest Suite (auto-detected)",
                type="pytest_pass",
                command="pytest -v backend/tests",
                weight=3.0,
                required=True,
                timeout_seconds=120,
            )
        )

    # 2. Python source compilation / syntax check
    for src_dir_name in ("app", "src", "backend/app"):
        if (project_dir / src_dir_name).is_dir() and any((project_dir / src_dir_name).rglob("*.py")):
            verifiers.append(
                VerificationCheck(
                    id=f"auto_py_compile_{src_dir_name.replace('/', '_')}",
                    name=f"Python Syntax Check ({src_dir_name}/)",
                    type="command_exit_code",
                    command=f"python -m compileall -q {src_dir_name}",
                    weight=1.5,
                    required=True,
                    timeout_seconds=60,
                )
            )
            break

    # 3. Node.js / Frontend build check (when package.json + node_modules exist)
    for pkg_rel in ("package.json", "frontend/package.json"):
        pkg_path = project_dir / pkg_rel
        if pkg_path.exists():
            try:
                pkg_data = json.loads(pkg_path.read_text(encoding="utf-8", errors="replace"))
                scripts = pkg_data.get("scripts") or {}
                pkg_dir = pkg_path.parent
                if "build" in scripts and (pkg_dir / "node_modules").is_dir():
                    cmd = "npm run build" if pkg_rel == "package.json" else "npm --prefix frontend run build"
                    verifiers.append(
                        VerificationCheck(
                            id="auto_npm_build",
                            name=f"Frontend Build ({pkg_rel})",
                            type="command_exit_code",
                            command=cmd,
                            weight=2.0,
                            required=True,
                            timeout_seconds=120,
                        )
                    )
                    break
            except Exception:
                pass

    # 4. TBA / Documentation deliverables if present
    if (project_dir / "WORKFLOWS_AND_DELIVERY_DOCS.md").exists():
        verifiers.append(
            VerificationCheck(
                id="auto_workflows_mermaid",
                name="Mermaid Workflow Diagrams Valid",
                type="mermaid_diagram_check",
                target_path="WORKFLOWS_AND_DELIVERY_DOCS.md",
                pattern="flowchart,sequenceDiagram,stateDiagram",
                weight=2.0,
                required=False,
                timeout_seconds=20,
            )
        )
    if (project_dir / "EPICS_AND_USER_STORIES.md").exists():
        verifiers.append(
            VerificationCheck(
                id="auto_user_stories_invest",
                name="User Stories 3Cs & INVEST Compliance",
                type="user_story_invest_check",
                target_path="EPICS_AND_USER_STORIES.md",
                weight=2.0,
                required=False,
                timeout_seconds=20,
            )
        )

    # 5. Fallback project config / README presence check
    for cfg_file in ("pyproject.toml", "requirements.txt", "package.json", "README.md"):
        if (project_dir / cfg_file).exists():
            verifiers.append(
                VerificationCheck(
                    id=f"auto_exists_{cfg_file.replace('.', '_')}",
                    name=f"Project File Present ({cfg_file})",
                    type="file_exists",
                    target_path=cfg_file,
                    weight=1.0,
                    required=False,
                    timeout_seconds=10,
                )
            )
            break

    return verifiers


def run_deterministic_verifiers(
    verifiers: List[VerificationCheck],
    sandbox_dir: Path,
    git_diff: str,
) -> Tuple[List[VerifierCheckResult], float, bool]:
    """Run all deterministic checks in the sandbox and return (results, weighted_score_0_100, all_required_passed)."""
    if not verifiers:
        return [], 100.0, True

    results: List[VerifierCheckResult] = []
    total_weight = 0.0
    earned_weight = 0.0
    all_required_passed = True
    bootstrapped_venv = False

    def _run_cmd_in_project(cmd_str: str, timeout_s: int, project_py: Optional[Path]) -> subprocess.CompletedProcess:
        py_exec = str(project_py) if project_py else sys.executable
        env = build_project_env(project_py)
        stripped = cmd_str.strip()
        if stripped.startswith("pytest"):
            args = [py_exec, "-m", *stripped.split()]
            return subprocess.run(
                args,
                cwd=str(sandbox_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                encoding="utf-8",
                errors="replace",
            )
        if stripped.startswith("python ") or stripped.startswith("python3 "):
            parts = stripped.split()
            args = [py_exec, *parts[1:]]
            return subprocess.run(
                args,
                cwd=str(sandbox_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                encoding="utf-8",
                errors="replace",
            )
        return subprocess.run(
            cmd_str,
            cwd=str(sandbox_dir),
            env=env,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            encoding="utf-8",
            errors="replace",
        )

    for check in verifiers:
        t0 = time.perf_counter()
        passed = False
        exit_code = None
        output = ""

        try:
            if check.type in ("command_exit_code", "pytest_pass"):
                cmd_str = check.command or ("pytest -v" if check.type == "pytest_pass" else "echo ok")
                proj_py = find_project_python(sandbox_dir)
                proc = _run_cmd_in_project(cmd_str, check.timeout_seconds, proj_py)
                combined_out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()

                # Auto-bootstrap project .venv once if a Python/pytest check fails due to missing modules
                is_py_cmd = cmd_str.strip().startswith(("pytest", "python ", "python3 "))
                missing_module = (
                    "ModuleNotFoundError" in combined_out
                    or "No module named" in combined_out
                    or "ImportError" in combined_out
                )
                if proc.returncode != 0 and is_py_cmd and missing_module and not bootstrapped_venv:
                    bootstrapped_venv = True
                    new_py, setup_note = bootstrap_project_python_env(sandbox_dir)
                    if new_py:
                        proc = _run_cmd_in_project(cmd_str, check.timeout_seconds, new_py)
                        retry_out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
                        combined_out = f"[Auto-Setup: {setup_note}]\n{retry_out}".strip()

                exit_code = proc.returncode
                passed = proc.returncode == 0
                output = combined_out[:1500]

            elif check.type == "file_exists":
                target = sandbox_dir / (check.target_path or "")
                passed = target.exists()
                output = f"File '{check.target_path}' exists: {passed}"

            elif check.type in ("file_contains_regex", "file_not_contains_regex"):
                target = sandbox_dir / (check.target_path or "")
                if not target.exists():
                    passed = False
                    output = f"Target file '{check.target_path}' does not exist"
                else:
                    content = target.read_text(encoding="utf-8", errors="replace")
                    found = bool(re.search(check.pattern or "", content, re.MULTILINE))
                    passed = found if check.type == "file_contains_regex" else (not found)
                    output = (
                        f"Pattern '{check.pattern}' in '{check.target_path}': found={found} -> passed={passed}"
                    )

            elif check.type == "git_diff_contains":
                found = bool(re.search(check.pattern or "", git_diff, re.MULTILINE))
                passed = found
                output = f"Git diff contains '{check.pattern}': {passed}"

            elif check.type == "git_diff_max_lines":
                changed_lines = [
                    ln
                    for ln in git_diff.splitlines()
                    if (ln.startswith("+") or ln.startswith("-"))
                    and not ln.startswith("+++")
                    and not ln.startswith("---")
                ]
                limit = check.max_lines or 100
                passed = len(changed_lines) <= limit
                output = f"Diff modified {len(changed_lines)} lines (max allowed: {limit})"

            elif check.type == "markdown_sections_present":
                target = sandbox_dir / (check.target_path or "")
                if not target.exists():
                    passed = False
                    output = f"Target document '{check.target_path}' does not exist"
                else:
                    content = target.read_text(encoding="utf-8", errors="replace")
                    content_lower = content.lower()
                    required_sections = [
                        s.strip() for s in (check.pattern or "").split(",") if s.strip()
                    ]
                    missing = [s for s in required_sections if s.lower() not in content_lower]
                    passed = len(missing) == 0
                    output = (
                        f"All {len(required_sections)} required sections present in '{check.target_path}': "
                        f"{', '.join(required_sections)}"
                        if passed
                        else f"Missing required sections in '{check.target_path}': {', '.join(missing)}"
                    )

            elif check.type == "user_story_invest_check":
                target = sandbox_dir / (check.target_path or "EPICS_AND_USER_STORIES.md")
                if not target.exists():
                    passed = False
                    output = f"User Story specification '{target.name}' does not exist"
                else:
                    content = target.read_text(encoding="utf-8", errors="replace")
                    # Strip markdown bold/italic/code/blockquote/bullet markers so multi-line formatted stories & Gherkin match cleanly
                    clean_md = re.sub(r"[\*_`>]", "", content)
                    # 1. Connextra role-feature-benefit format ("As a ... I want ... So that ...", single-line or multi-line)
                    connextra_matches = re.findall(
                        r"\bas an?\s+[\s\S]{3,220}?\bi want\b[\s\S]{3,350}?\bso that\b[^\n]+",
                        clean_md,
                        flags=re.IGNORECASE,
                    )
                    # Exclude template placeholder examples like "<persona>" or "<goal>"
                    connextra_matches = [
                        m for m in connextra_matches if "<persona>" not in m.lower() and "<role>" not in m.lower()
                    ]
                    # 2. Ron Jeffries' 3 Cs: Card (US- ID & Epic link), Conversation (Dev notes), Confirmation (Given/When/Then BDD + TC-)
                    has_card_ids = bool(re.search(r"\bEPIC-\d+", content)) and bool(
                        re.search(r"\bUS-\d+", content)
                    )
                    has_conversation_dev = bool(
                        re.search(r"(conversation|developer notes|technical constraints|data rules)", content, re.I)
                    )
                    bdd_matches = re.findall(
                        r"\bgiven\s+[\s\S]{3,400}?\bwhen\s+[\s\S]{3,400}?\bthen\s+[^\n]+",
                        clean_md,
                        flags=re.IGNORECASE,
                    )
                    has_qa_test_cases = bool(re.search(r"\bTC-\d+", content))
                    # 3. Bill Wake's INVEST criteria
                    invest_terms = ["independent", "negotiable", "valuable", "estimable", "small", "testable"]
                    has_invest = all(term in content.lower() for term in invest_terms)
                    # 4. Definition of Ready / Definition of Done
                    has_dor_dod = "definition of ready" in content.lower() and "definition of done" in content.lower()

                    diagnostics = [
                        f"Connextra ('As a... I want... So that...') stories found: {len(connextra_matches)} (req >= 2)",
                        f"3Cs Card (EPIC-xx & US-xxx IDs): {'OK' if has_card_ids else 'MISSING'}",
                        f"3Cs Conversation (Development Team technical/domain rules): {'OK' if has_conversation_dev else 'MISSING'}",
                        f"3Cs Confirmation (BDD Given/When/Then scenarios): {len(bdd_matches)} found, QA Test Cases (TC-xxx): {'OK' if has_qa_test_cases else 'MISSING'}",
                        f"Bill Wake's INVEST Checklist (I-N-V-E-S-T): {'OK' if has_invest else 'MISSING'}",
                        f"Definition of Ready (DoR) & Definition of Done (DoD): {'OK' if has_dor_dod else 'MISSING'}",
                    ]
                    passed = (
                        len(connextra_matches) >= 2
                        and has_card_ids
                        and has_conversation_dev
                        and len(bdd_matches) >= 2
                        and has_qa_test_cases
                        and has_invest
                        and has_dor_dod
                    )
                    output = "\n".join(diagnostics)

            elif check.type == "mermaid_diagram_valid":
                target = sandbox_dir / (check.target_path or "WORKFLOWS_AND_DELIVERY_DOCS.md")
                if not target.exists():
                    passed = False
                    output = f"Workflow document '{target.name}' does not exist"
                else:
                    content = target.read_text(encoding="utf-8", errors="replace")
                    blocks = re.findall(r"```mermaid\s+([\s\S]+?)```", content)
                    valid_headers = ("flowchart", "graph", "sequencediagram", "statediagram", "erdiagram")
                    valid_blocks = [
                        b
                        for b in blocks
                        if any(
                            b.strip().lower().startswith(h)
                            for h in valid_headers
                        )
                        and ("-->" in b or "->>" in b)
                    ]
                    passed = len(valid_blocks) >= 1
                    output = (
                        f"Found {len(valid_blocks)} valid Mermaid workflow diagram(s) in '{target.name}'"
                        if passed
                        else f"No valid Mermaid workflow diagrams found in '{target.name}'"
                    )

        except subprocess.TimeoutExpired:
            passed = False
            exit_code = -1
            output = f"Command timed out after {check.timeout_seconds}s"
        except Exception as exc:
            passed = False
            output = f"Verifier exception: {exc}"

        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        results.append(
            VerifierCheckResult(
                check_id=check.id,
                name=check.name,
                type=check.type,
                passed=passed,
                required=check.required,
                weight=check.weight,
                exit_code=exit_code,
                output=output,
                duration_ms=dur_ms,
            )
        )

        total_weight += check.weight
        if passed:
            earned_weight += check.weight
        elif check.required:
            all_required_passed = False

    score = round((earned_weight / total_weight) * 100.0, 2) if total_weight > 0 else 100.0
    return results, score, all_required_passed
