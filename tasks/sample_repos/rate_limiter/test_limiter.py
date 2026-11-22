"""Unit tests for SlidingWindowRateLimiter."""

from limiter import SlidingWindowRateLimiter


def test_basic_allowance_and_rejection():
    rl = SlidingWindowRateLimiter(max_requests=2, window_seconds=10.0, burst_allowance=1)
    # Total capacity = 2 + 1 = 3
    assert rl.allow_request("client_a", 1.0) is True
    assert rl.allow_request("client_a", 2.0) is True
    assert rl.allow_request("client_a", 3.0) is True
    assert rl.remaining_quota("client_a", 3.5) == 0
    assert rl.allow_request("client_a", 4.0) is False


def test_window_expiration_frees_quota():
    rl = SlidingWindowRateLimiter(max_requests=2, window_seconds=10.0, burst_allowance=0)
    assert rl.allow_request("client_a", 5.0) is True
    assert rl.allow_request("client_a", 8.0) is True
    assert rl.allow_request("client_a", 14.9) is False
    # At timestamp 15.0, the request at 5.0 is >= 10.0s old (5.0 <= 15.0 - 10.0) and must be evicted
    assert rl.remaining_quota("client_a", 15.0) == 1
    assert rl.allow_request("client_a", 15.0) is True


def test_independent_clients():
    rl = SlidingWindowRateLimiter(max_requests=1, window_seconds=5.0, burst_allowance=0)
    assert rl.allow_request("c1", 1.0) is True
    assert rl.allow_request("c1", 2.0) is False
    assert rl.allow_request("c2", 2.0) is True
