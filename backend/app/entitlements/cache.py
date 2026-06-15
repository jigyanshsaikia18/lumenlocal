"""Short-TTL cache for resolved entitlement sets (PRD §5 FT-2).

The API gateway resolves a client's (and optionally a location's) feature set on
*every* request. Reading the four override layers from Postgres each time would put
the toggle engine on the hot path of all traffic. This cache memoises the resolved
set for a short window so the common case is in-process, while still honouring the
product requirement that a toggle change "take effect in < 1 minute" with no deploy.

Two mechanisms keep the cached view fresh:

1. **TTL expiry** (``ttl_seconds``, default from settings) — the cross-worker
   guarantee. Any entry older than the TTL is re-resolved from the DB. This bounds
   staleness even on a node that never served the toggle write.
2. **Explicit invalidation** — the override-write path calls
   :meth:`invalidate_client` so the node that served the toggle reflects it
   immediately, ahead of the TTL.

The cache stores only the pure resolved dict (no DB handles), so it is safe to keep
as a process-global shared across requests. Resolution itself is injected as a
``loader`` callable, which keeps this module free of any DB dependency and trivially
unit-testable with a fake clock.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from uuid import UUID

from app.core.config import settings
from app.entitlements.resolver import ResolvedFeature

# (client_id, location_id) — location_id is None for client-scope resolution.
CacheKey = tuple[UUID, UUID | None]
Resolved = dict[str, ResolvedFeature]
Loader = Callable[[UUID, UUID | None], Resolved]


class TtlEntitlementCache:
    """In-process, TTL-bounded cache of resolved feature sets, keyed by scope."""

    def __init__(
        self,
        *,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        # key -> (stored_at_monotonic, resolved set)
        self._entries: dict[CacheKey, tuple[float, Resolved]] = {}

    def resolve(
        self, client_id: UUID, location_id: UUID | None, loader: Loader
    ) -> Resolved:
        """Return the cached resolved set, refreshing via ``loader`` past the TTL."""
        key: CacheKey = (client_id, location_id)
        now = self._clock()
        with self._lock:
            hit = self._entries.get(key)
            if hit is not None and (now - hit[0]) < self._ttl:
                return hit[1]
        # Resolve outside the lock — loading hits the DB and must not serialise traffic.
        resolved = loader(client_id, location_id)
        with self._lock:
            self._entries[key] = (self._clock(), resolved)
        return resolved

    def invalidate_client(self, client_id: UUID) -> None:
        """Drop every cached entry for ``client_id`` (client- and location-scoped).

        Called by the toggle-write path: a client-level change affects the client
        scope *and* every location scope under it, so all of the client's keys are
        evicted and re-resolved on next read.
        """
        with self._lock:
            for key in [k for k in self._entries if k[0] == client_id]:
                del self._entries[key]

    def clear(self) -> None:
        """Empty the cache entirely (used between tests)."""
        with self._lock:
            self._entries.clear()


# Process-global cache shared by all requests. TTL comes from settings so it is
# tunable per environment without code changes.
entitlement_cache = TtlEntitlementCache(
    ttl_seconds=settings.entitlement_cache_ttl_seconds
)
