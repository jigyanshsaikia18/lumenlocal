"""Rate limiting for automated critical-field reverts (P4A-2, CLAUDE.md).

Rapid automated edits to critical fields are themselves a documented suspension
trigger, so an ``auto_revert_critical`` location is capped: at most
:data:`DEFAULT_MAX_REVERTS` automated reverts per location within a rolling
:data:`DEFAULT_WINDOW_SECONDS`. Beyond the cap the service falls back to an alert
rather than continuing to fight a persistent edit (which would look exactly like
the automation Google penalises). This is legitimate change-management throttling,
**not** detection-evasion (CLAUDE.md): the cap protects the profile, it does not
disguise writes as organic.

The limiter is a small injectable seam (Protocol) with an in-memory sliding-window
implementation and an injectable clock, so the policy is deterministic in tests. A
Redis-backed implementation can replace it later without touching the service.
"""
from __future__ import annotations

import threading
from collections import defaultdict, deque
from time import time as _wall_time
from typing import Callable, Protocol
from uuid import UUID

DEFAULT_MAX_REVERTS = 3
DEFAULT_WINDOW_SECONDS = 24 * 60 * 60  # 24h


class RevertRateLimiter(Protocol):
    """Throttles automated reverts per location."""

    def allow(self, location_id: UUID) -> bool:
        """True if another automated revert is permitted for ``location_id`` now."""
        ...

    def record(self, location_id: UUID) -> None:
        """Register that an automated revert just happened for ``location_id``."""
        ...


class InMemoryRevertRateLimiter:
    """Sliding-window limiter backed by per-location timestamp deques.

    Single-process only (fine for the worker and the test suite); swap for a shared
    store in production. ``clock`` defaults to wall time but is injectable so tests
    can advance it deterministically.
    """

    def __init__(
        self,
        *,
        max_reverts: int = DEFAULT_MAX_REVERTS,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        clock: Callable[[], float] = _wall_time,
    ) -> None:
        self._max = max_reverts
        self._window = window_seconds
        self._clock = clock
        self._events: dict[UUID, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, stamps: deque[float], now: float) -> None:
        cutoff = now - self._window
        while stamps and stamps[0] <= cutoff:
            stamps.popleft()

    def allow(self, location_id: UUID) -> bool:
        now = self._clock()
        with self._lock:
            stamps = self._events[location_id]
            self._prune(stamps, now)
            return len(stamps) < self._max

    def record(self, location_id: UUID) -> None:
        now = self._clock()
        with self._lock:
            stamps = self._events[location_id]
            self._prune(stamps, now)
            stamps.append(now)
