"""Dead-letter queue: where tasks go after they have exhausted their retries.

A task that keeps failing should not vanish silently or loop forever. Once the
base task's retry budget is spent, Celery invokes ``on_failure`` and we park a
JSON record of the attempt on a Redis list. Operators (or a future replay tool)
can inspect :func:`read` to see what failed and why, then re-enqueue once the
root cause is fixed. The DLQ is observe-and-replay, never auto-retry.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.jobs.store import JobStore


def record(
    store: JobStore,
    *,
    task_name: str,
    task_id: str | None,
    tenant_id: str | None,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    exc: BaseException,
) -> dict[str, Any]:
    """Append a failure record to the dead-letter queue and return it."""
    entry: dict[str, Any] = {
        "task_name": task_name,
        "task_id": task_id,
        "tenant_id": tenant_id,
        # repr() so un-JSON-able args (UUIDs, models) still serialise safely.
        "args": [repr(a) for a in args],
        "kwargs": {k: repr(v) for k, v in kwargs.items()},
        "exc_type": type(exc).__name__,
        "exc": str(exc),
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    store.rpush(settings.jobs_dead_letter_key, json.dumps(entry))
    return entry


def read(store: JobStore, limit: int = 100) -> list[dict[str, Any]]:
    """Return up to ``limit`` dead-letter records, oldest first."""
    raw = store.lrange(settings.jobs_dead_letter_key, 0, limit - 1)
    return [json.loads(item) for item in raw]


def depth(store: JobStore) -> int:
    """How many records are currently parked in the dead-letter queue."""
    return store.llen(settings.jobs_dead_letter_key)
