"""Per-tenant fairness: a cap on how many tasks one tenant runs concurrently.

The heavy load in this platform is scan/sampling fan-out, and a single large
agency can enqueue thousands of tasks at once. Without a guard those tasks would
fill every worker slot and starve smaller tenants
(02_Technical_Architecture §8). This module is the admission gate:

* :func:`acquire` atomically bumps a per-tenant in-flight counter and returns
  ``False`` if the tenant is already at its cap;
* the base task reacts to ``False`` by re-queuing the task with a short delay,
  freeing the worker for someone else;
* :func:`release` decrements the counter when the task finishes (success or
  failure).

The counter carries a TTL refreshed on every acquire, so if a worker dies
mid-task and never releases, the slot is reclaimed rather than leaking and
permanently shrinking the tenant's effective quota. This is cooperative fairness
layered on top of Celery's own ``worker_prefetch_multiplier = 1`` /
``task_acks_late`` settings (which stop a worker greedily prefetching one
tenant's backlog).
"""
from __future__ import annotations

from app.jobs.store import JobStore

_PREFIX = "jobs:inflight:"


def _k(tenant_id: str) -> str:
    return f"{_PREFIX}{tenant_id}"


def acquire(store: JobStore, tenant_id: str, cap: int, ttl: int) -> bool:
    """Try to take an in-flight slot for ``tenant_id``.

    Returns ``True`` if a slot was granted (caller must later :func:`release`),
    ``False`` if the tenant is already running ``cap`` tasks.
    """
    key = _k(tenant_id)
    current = store.incr(key)
    if current > cap:
        # Over the cap — give the slot straight back and tell the caller to yield.
        store.decr(key)
        return False
    store.expire(key, ttl)
    return True


def release(store: JobStore, tenant_id: str) -> None:
    """Return an in-flight slot. Guards against underflow from double-release."""
    key = _k(tenant_id)
    if store.decr(key) < 0:
        store.set(key, "0")


def in_flight(store: JobStore, tenant_id: str) -> int:
    """Number of slots currently held by ``tenant_id`` (0 if none)."""
    return int(store.get(_k(tenant_id)) or "0")
