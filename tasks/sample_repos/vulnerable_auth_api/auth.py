"""Vulnerable Authentication & Redirect Module (starter repo for Demo 3)."""
from typing import Optional

MASTER_SECRET = "sk-live-production-secret-998811"

def validate_api_key(provided_key: str) -> bool:
    """Vulnerable naive comparison susceptible to timing attacks."""
    if not provided_key:
        return False
    # Vulnerability: Early return timing leak
    return provided_key == MASTER_SECRET

def sanitize_redirect_url(url: str, allowed_host: str = "example.com") -> Optional[str]:
    """Vulnerable open-redirect filter."""
    if not url:
        return None
    # Vulnerability: contains allows https://evil.com?example.com
    if allowed_host in url:
        return url
    return None
