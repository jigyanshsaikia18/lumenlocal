"""The auto-revert rate limiter (P4A-2): bounded reverts per location per window."""
from uuid import uuid4

from app.protection import InMemoryRevertRateLimiter


class _Clock:
    """Manually-advanced clock so window behaviour is deterministic."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_allows_up_to_cap_then_blocks_within_window():
    limiter = InMemoryRevertRateLimiter(max_reverts=2, window_seconds=3600)
    loc = uuid4()

    assert limiter.allow(loc) is True
    limiter.record(loc)
    assert limiter.allow(loc) is True
    limiter.record(loc)
    # Cap reached for this window.
    assert limiter.allow(loc) is False


def test_window_slides_so_old_reverts_expire():
    clock = _Clock()
    limiter = InMemoryRevertRateLimiter(max_reverts=1, window_seconds=3600, clock=clock)
    loc = uuid4()

    limiter.record(loc)
    assert limiter.allow(loc) is False

    clock.advance(3601)  # the recorded revert is now outside the window
    assert limiter.allow(loc) is True


def test_limits_are_per_location():
    limiter = InMemoryRevertRateLimiter(max_reverts=1, window_seconds=3600)
    a, b = uuid4(), uuid4()

    limiter.record(a)
    assert limiter.allow(a) is False
    # A different location is unaffected.
    assert limiter.allow(b) is True
