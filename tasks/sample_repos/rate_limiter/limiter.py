"""Sliding window rate limiter starter module."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque, Dict


class SlidingWindowRateLimiter:
    """Rate limiter using a per-client sliding time window with burst allowance."""

    def __init__(self, max_requests: int, window_seconds: float, burst_allowance: int = 0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.burst_allowance = burst_allowance
        self._history: Dict[str, Deque[float]] = defaultdict(deque)

    def allow_request(self, client_id: str, timestamp: float) -> bool:
        """Return True and record timestamp if client is within quota at `timestamp`."""
        raise NotImplementedError("TODO: implement sliding window rate limit check")

    def remaining_quota(self, client_id: str, timestamp: float) -> int:
        """Return remaining allowed requests for `client_id` at `timestamp`."""
        raise NotImplementedError("TODO: implement remaining_quota calculation")
