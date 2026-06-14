"""Idempotency for tasks: run the same logical unit of work at most once.

A task is made idempotent by passing an ``idempotency_key`` (a stable,
caller-chosen string — e.g. ``f"scan:{location_id}:{date}"``). The framework
takes a **claim** on that key before running:

* first submission  → claim succeeds → the task runs and the key is marked
  ``done`` on success;
* duplicate submission while the first is still ``pending`` or after it is
  ``done`` → claim fails → the task body is skipped.

A *retry* of an already-claimed task is **not** a duplicate — the base task
detects retries by ``request.retries`` and bypasses the claim check, so a
transient failure still gets its retries. The claim is only released on final
failure, so a genuinely new submission can run later once the problem is fixed.

Keys are namespaced and carry a TTL so the ledger does not grow without bound.
"""
from __future__ import annotations

from app.jobs.store import JobStore

_PREFIX = "jobs:idem:"
PENDING = "pending"
DONE = "done"


def _k(key: str) -> str:
    return f"{_PREFIX}{key}"


def claim(store: JobStore, key: str, ttl: int) -> bool:
    """Atomically take the claim. ``True`` if we may run, ``False`` if duplicate."""
    return store.set_if_absent(_k(key), PENDING, ttl)


def mark_done(store: JobStore, key: str, ttl: int) -> None:
    """Record successful completion so later duplicates are suppressed."""
    store.set(_k(key), DONE, ttl)


def release(store: JobStore, key: str) -> None:
    """Drop the claim (used after final failure) so a resubmission can run."""
    store.delete(_k(key))


def state(store: JobStore, key: str) -> str | None:
    """Current claim state: ``"pending"``, ``"done"`` or ``None`` (no claim)."""
    return store.get(_k(key))
