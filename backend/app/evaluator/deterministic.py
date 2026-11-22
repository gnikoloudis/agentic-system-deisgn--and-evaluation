"""Layer 1: Deterministic Outcome Graders (Pytest, Shell Commands, File & Git Diff Assertions)."""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

from app.schemas.evaluation import VerifierCheckResult
from app.schemas.task import VerificationCheck


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

    for check in verifiers:
        t0 = time.perf_counter()
        passed = False
        exit_code = None
        output = ""

        try:
            if check.type in ("command_exit_code", "pytest_pass"):
                cmd_str = check.command or ("pytest -v" if check.type == "pytest_pass" else "echo ok")
                # Use current python interpreter for pytest to guarantee environment consistency on Windows
                if cmd_str.strip().startswith("pytest"):
                    args = [sys.executable, "-m", *cmd_str.strip().split()]
                    proc = subprocess.run(
                        args,
                        cwd=str(sandbox_dir),
                        capture_output=True,
                        text=True,
                        timeout=check.timeout_seconds,
                        encoding="utf-8",
                        errors="replace",
                    )
                else:
                    proc = subprocess.run(
                        cmd_str,
                        cwd=str(sandbox_dir),
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=check.timeout_seconds,
                        encoding="utf-8",
                        errors="replace",
                    )
                exit_code = proc.returncode
                passed = proc.returncode == 0
                output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()[:1500]

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
                    clean_md = re.sub(r"[\*_`]", "", content)
                    # 1. Connextra role-feature-benefit format ("As a ... I want ... So that ...")
                    connextra_matches = re.findall(
                        r"as an?\s+[^\n]+?,\s*i want\s+[^\n]+?,\s*so that\s+[^\n]+",
                        clean_md,
                        flags=re.IGNORECASE,
                    )
                    # 2. Ron Jeffries' 3 Cs: Card (US- ID & Epic link), Conversation (Dev notes), Confirmation (Given/When/Then BDD + TC-)
                    has_card_ids = bool(re.search(r"\bEPIC-\d+", content)) and bool(
                        re.search(r"\bUS-\d+", content)
                    )
                    has_conversation_dev = bool(
                        re.search(r"(conversation|developer notes|technical constraints|data rules)", content, re.I)
                    )
                    bdd_matches = re.findall(
                        r"given\s+[^\n]+?when\s+[^\n]+?then\s+[^\n]+",
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
