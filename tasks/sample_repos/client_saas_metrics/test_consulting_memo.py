"""Automated consulting deliverable verification tests for AcmeCloud strategy case."""

from pathlib import Path


MEMO_PATH = Path("EXECUTIVE_MEMO.md")


def test_executive_memo_file_created():
    assert MEMO_PATH.exists(), "EXECUTIVE_MEMO.md must be created in the workspace root"
    content = MEMO_PATH.read_text(encoding="utf-8")
    assert len(content.strip()) >= 400, "EXECUTIVE_MEMO.md must be a substantive executive report (>= 400 chars)"


def test_cites_accurate_financial_and_segment_metrics():
    content = MEMO_PATH.read_text(encoding="utf-8")
    # Must cite total ARR ($24.5M or 24,500,000), SMB 38% churn, Enterprise 118% NDR, and 64% Gross Margin
    assert "24.5" in content or "24,500,000" in content, "Must cite Total ARR ($24.5M)"
    assert "38%" in content, "Must cite SMB annualized churn rate (38%)"
    assert "118%" in content, "Must cite Enterprise Net Dollar Retention (118%)"
    assert "64%" in content, "Must cite current Gross Margin (64%)"
    assert "1.8" in content and "5.4" in content, "Must cite SMB (1.8) and Enterprise (5.4) LTV:CAC ratios"


def test_contains_mece_sections_and_90_day_roadmap():
    content = MEMO_PATH.read_text(encoding="utf-8").lower()
    assert "executive summary" in content, "Missing Executive Summary section"
    assert "enterprise" in content and "smb" in content, "Must compare Enterprise and SMB segments"
    assert "90" in content or "roadmap" in content or "action" in content, "Must include a 90-Day Turnaround Roadmap"
