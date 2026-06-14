"""The tiny key/value substrate the job framework coordinates through.

Idempotency claims, per-tenant in-flight counters, and the dead-letter queue all
need a small set of atomic primitives (atomic incr/decr, set-if-absent, list
append). In production that is **Redis** — the same broker Celery already uses.

In tests we run Celery in *eager* mode with no broker at all, so the factory
swaps in a process-local :class:`InMemoryStore` that implements the identical
contract with a lock. That keeps the framework's tests hermetic (no infra
required, matching ``tests/test_health.py``) while exercising the real code
paths: the only thing that changes is where the bytes live.

Only the handful of operations the framework actually uses are exposed; this is
deliberately **not** a general Redis wrapper.
"""
from __future__ import annotations

import threading
import time
from typing import Protocol


class JobStore(Protocol):
    """The atomic primitives the job framework relies on."""

    def incr(self, key: str) -> int: ...
    def decr(self, key: str) -> int: ...
    def expire(self, key: str, ttl: int) -> None: ...
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl: int | None = None) -> None: ...
    def set_if_absent(self, key: str, value: str, ttl: int | None = None) -> bool: ...
    def delete(self, key: str) -> None: ...
    def rpush(self, key: str, value: str) -> int: ...
    def lrange(self, key: str, start: int, stop: int) -> list[str]: ...
    def llen(self, key: str) -> int: ...


class InMemoryStore:
    """Thread-safe, process-local stand-in for Redis used in eager-mode tests.

    TTLs are honoured lazily (a key is treated as gone once expired) so that
    expiry-dependent behaviour can still be asserted in tests if needed. It is
    intentionally not shared across processes — it only has to back a single
    eager worker running inside the test process.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._values: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}
        self._expiry: dict[str, float] = {}

    # -- internal helpers (call only while holding the lock) ---------------
    def _expired(self, key: str) -> bool:
        exp = self._expiry.get(key)
        if exp is not None and exp <= time.monotonic():
            self._values.pop(key, None)
            self._lists.pop(key, None)
            self._expiry.pop(key, None)
            return True
        return False

    # -- counters ----------------------------------------------------------
    def incr(self, key: str) -> int:
        with self._lock:
            self._expired(key)
            new = int(self._values.get(key, "0")) + 1
            self._values[key] = str(new)
            return new

    def decr(self, key: str) -> int:
        with self._lock:
            self._expired(key)
            new = int(self._values.get(key, "0")) - 1
            self._values[key] = str(new)
            return new

    def expire(self, key: str, ttl: int) -> None:
        with self._lock:
            if key in self._values or key in self._lists:
                self._expiry[key] = time.monotonic() + ttl

    # -- scalars -----------------------------------------------------------
    def get(self, key: str) -> str | None:
        with self._lock:
            if self._expired(key):
                return None
            return self._values.get(key)

    def set(self, key: str, value: str, ttl: int | None = None) -> None:
        with self._lock:
            self._values[key] = value
            if ttl is not None:
                self._expiry[key] = time.monotonic() + ttl
            else:
                self._expiry.pop(key, None)

    def set_if_absent(self, key: str, value: str, ttl: int | None = None) -> bool:
        with self._lock:
            self._expired(key)
            if key in self._values:
                return False
            self._values[key] = value
            if ttl is not None:
                self._expiry[key] = time.monotonic() + ttl
            return True

    def delete(self, key: str) -> None:
        with self._lock:
            self._values.pop(key, None)
            self._lists.pop(key, None)
            self._expiry.pop(key, None)

    # -- lists -------------------------------------------------------------
    def rpush(self, key: str, value: str) -> int:
        with self._lock:
            self._expired(key)
            self._lists.setdefault(key, []).append(value)
            return len(self._lists[key])

    def lrange(self, key: str, start: int, stop: int) -> list[str]:
        with self._lock:
            if self._expired(key):
                return []
            items = self._lists.get(key, [])
            # Redis LRANGE is inclusive of stop; -1 means "to the end".
            if stop == -1:
                return items[start:]
            return items[start : stop + 1]

    def llen(self, key: str) -> int:
        with self._lock:
            if self._expired(key):
                return 0
            return len(self._lists.get(key, []))

    def clear(self) -> None:
        """Drop all state — used by tests between cases."""
        with self._lock:
            self._values.clear()
            self._lists.clear()
            self._expiry.clear()


class RedisStore:
    """Production store backed by Redis (``decode_responses`` so we deal in str)."""

    def __init__(self, url: str) -> None:
        import redis  # local import: avoids a hard redis dependency in eager tests

        self._r = redis.Redis.from_url(url, decode_responses=True)

    def incr(self, key: str) -> int:
        return int(self._r.incr(key))

    def decr(self, key: str) -> int:
        return int(self._r.decr(key))

    def expire(self, key: str, ttl: int) -> None:
        self._r.expire(key, ttl)

    def get(self, key: str) -> str | None:
        return self._r.get(key)

    def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self._r.set(key, value, ex=ttl)

    def set_if_absent(self, key: str, value: str, ttl: int | None = None) -> bool:
        return bool(self._r.set(key, value, nx=True, ex=ttl))

    def delete(self, key: str) -> None:
        self._r.delete(key)

    def rpush(self, key: str, value: str) -> int:
        return int(self._r.rpush(key, value))

    def lrange(self, key: str, start: int, stop: int) -> list[str]:
        return list(self._r.lrange(key, start, stop))

    def llen(self, key: str) -> int:
        return int(self._r.llen(key))


# A single eager-mode store shared by producer and (synchronous) consumer within
# one test process, so a claim taken by .delay() is visible to the task body.
_memory_store = InMemoryStore()


def get_store() -> JobStore:
    """Return the store appropriate to the current Celery mode.

    Eager mode (tests) → the shared in-memory store; otherwise → Redis. The
    Celery import is deferred to call time so importing this module never pulls
    in the Celery app (and there is no import cycle).
    """
    from app.core.celery_app import celery_app

    if celery_app.conf.task_always_eager:
        return _memory_store

    from app.core.config import settings

    return RedisStore(settings.redis_url)


def reset_memory_store() -> None:
    """Clear the eager-mode store (test hygiene between cases)."""
    _memory_store.clear()
