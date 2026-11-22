"""Unit tests for token_validator.py."""

from token_validator import validate_token


def test_valid_token_future_expiry():
    payload = {"user_id": "u1", "expires_at": 2000, "scopes": "read,write,admin"}
    assert validate_token(payload, current_time=1500, required_scope="write") is True


def test_expired_token_exact_boundary():
    payload = {"user_id": "u1", "expires_at": 1500, "scopes": "read"}
    assert validate_token(payload, current_time=1500) is False


def test_expired_token_past():
    payload = {"user_id": "u1", "expires_at": 1400, "scopes": "read"}
    assert validate_token(payload, current_time=1500) is False


def test_scope_exact_match_rejects_substring():
    payload = {"user_id": "u1", "expires_at": 2000, "scopes": "readonly,billing:read"}
    assert validate_token(payload, current_time=1500, required_scope="read") is False


def test_scope_whitespace_handling():
    payload = {"user_id": "u1", "expires_at": 2000, "scopes": "read , write , profile"}
    assert validate_token(payload, current_time=1500, required_scope="write") is True
