"""Security regression and exploit tests for auth.py."""
import pytest
from auth import validate_api_key, sanitize_redirect_url, MASTER_SECRET

def test_valid_api_key():
    assert validate_api_key(MASTER_SECRET) is True

def test_invalid_api_key():
    assert validate_api_key("wrong-key-1234") is False

def test_open_redirect_bypass_blocked():
    # Exploitative attack payloads that must be rejected
    evil_url = "https://attacker.com/steal?token=1&fake=example.com"
    assert sanitize_redirect_url(evil_url, "example.com") is None

def test_legitimate_redirect_allowed():
    valid_url = "https://example.com/dashboard"
    assert sanitize_redirect_url(valid_url, "example.com") == valid_url
