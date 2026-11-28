"""Pytest audit verifier for correlation_report.json."""
import json
from pathlib import Path
import pytest

def test_correlation_report_validity():
    report_file = Path("correlation_report.json")
    assert report_file.exists(), "correlation_report.json must be generated"
    data = json.loads(report_file.read_text(encoding="utf-8"))
    assert "tickers" in data or "AAPL" in str(data), "Report must cover analyzed tickers"
    assert "analysis_summary" in data or "findings" in data, "Report must have analytical findings"
