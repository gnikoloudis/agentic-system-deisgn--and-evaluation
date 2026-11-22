"""Authentication token validator module (contains intentional bugs for benchmark evaluation)."""

from __future__ import annotations

from typing import Dict, Optional


def validate_token(
    token_Payload: Dict[str, object],
    current_time: int,
    required_scope: Optional[str] = None,
) -> bool:
    """Validate token payload expiration and optional required scope."""
    if not isinstance(token_Payload, dict):
        return False

    expires_at = token_Payload.get("expires_at")
    if not isinstance(expires_at, (int, float)):
        return False

    # BUG 1: Off-by-one boundary bug: when current_time == expires_at, it should be expired (False)
    if current_time > expires_at:
        return False

    if required_scope:
        raw_scopes = str(token_Payload.get("scopes", ""))
        # BUG 2: Substring check matches "read" inside "readonly" instead of splitting tokens
        if required_scope not in raw_scopes:
            return False

    return True
