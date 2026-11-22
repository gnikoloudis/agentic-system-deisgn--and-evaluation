"""Automated verification suite for Technical Business Analyst deliverables (EPICS_AND_USER_STORIES.md & WORKFLOWS_AND_DELIVERY_DOCS.md)."""

from pathlib import Path
import re


STORIES_PATH = Path("EPICS_AND_USER_STORIES.md")
WORKFLOWS_PATH = Path("WORKFLOWS_AND_DELIVERY_DOCS.md")


def test_both_ba_deliverable_documents_exist():
    assert STORIES_PATH.exists(), "EPICS_AND_USER_STORIES.md must be created"
    assert WORKFLOWS_PATH.exists(), "WORKFLOWS_AND_DELIVERY_DOCS.md must be created"


def test_user_stories_follow_wikipedia_standard_and_dev_qa_interface():
    text = STORIES_PATH.read_text(encoding="utf-8")
    clean_md = re.sub(r"[\*_`]", "", text)
    lower = text.lower()

    # 1. Connextra template ("As a ... I want ... So that ...")
    connextra = re.findall(r"as an?\s+[^\n]+?,\s*i want\s+[^\n]+?,\s*so that\s+[^\n]+", clean_md, re.I)
    assert len(connextra) >= 3, f"Expected at least 3 Connextra user stories, found {len(connextra)}"

    # 2. 3 Cs: Card, Conversation (Dev), Confirmation (QA Given/When/Then + TC- IDs)
    assert "conversation" in lower, "Missing 'Conversation' section for Development Team details"
    assert "confirmation" in lower or "acceptance criteria" in lower, "Missing 'Confirmation / Acceptance Criteria' for Testing Team"
    bdd = re.findall(r"given\s+[^\n]+?when\s+[^\n]+?then\s+[^\n]+", clean_md, re.I)
    assert len(bdd) >= 3, "Must include Given/When/Then BDD Acceptance Criteria scenarios for QA Testing"
    assert re.search(r"\bTC-\d+", text), "Must include explicit QA Test Case IDs (TC-xxx)"

    # 3. Bill Wake's INVEST checklist
    for term in ("independent", "negotiable", "valuable", "estimable", "small", "testable"):
        assert term in lower, f"Missing INVEST criterion '{term}' in EPICS_AND_USER_STORIES.md"

    # 4. Stakeholder Domain Rules & Traceability (BR-001..BR-005, 60 days, $25, $500, 10 MB, 45-day SLA)
    for br in ("BR-001", "BR-002", "BR-003", "BR-004", "BR-005"):
        assert br in text, f"Business Requirement {br} must be traced in EPICS_AND_USER_STORIES.md"
    assert "60" in text and "25" in text and "500" in text and "45" in text


def test_workflows_and_delivery_docs_contain_mermaid_and_data_dictionary():
    text = WORKFLOWS_PATH.read_text(encoding="utf-8")
    assert "```mermaid" in text, "WORKFLOWS_AND_DELIVERY_DOCS.md must include Mermaid workflow diagrams"
    assert "data dictionary" in text.lower() or "field" in text.lower(), "Must include Data Dictionary / Technical Delivery Spec"
