"""A trivial registered task that exercises the whole job framework.

This is the worked example called for by P2A-1: it enqueues and runs, and it
demonstrates the framework contract without doing any real work.

* ``add`` is a plain system task (no ``tenant_id``) — it skips the fairness gate
  and simply returns a result, proving enqueue → run → track end to end.
* ``echo`` accepts the framework's ``tenant_id`` and ``idempotency_key`` kwargs,
  so it can be used to demonstrate per-tenant fairness and at-most-once
  submission. ``fail_times`` lets a test drive the retry path: the task raises
  until it has failed that many times, then succeeds (the count lives in the
  store so it survives across retry attempts).

Real task modules in later phases follow the same shape: spread
``TENANT_TASK_OPTIONS`` and set ``base=TenantTask``.
"""
from __future__ import annotations

from typing import Any

from app.core.celery_app import celery_app
from app.jobs.base import TENANT_TASK_OPTIONS, TenantTask
from app.jobs.store import get_store

# Build the decorator options once: the shared retry/backoff policy plus our base.
_OPTS: dict[str, Any] = {**TENANT_TASK_OPTIONS, "base": TenantTask}


@celery_app.task(**_OPTS)
def add(self, x: int, y: int) -> int:  # noqa: ANN001 - `self` injected by bind=True
    """Add two numbers. A system task: no tenant, no fairness gate."""
    return x + y


@celery_app.task(**_OPTS)
def echo(self, message: str, *, tenant_id: str | None = None, fail_times: int = 0) -> dict[str, Any]:  # noqa: ANN001
    """Echo ``message`` back, optionally failing the first ``fail_times`` attempts.

    ``tenant_id`` (if given) routes the task through the per-tenant fairness gate.
    ``fail_times`` drives the retry/dead-letter path: a per-task counter in the
    store is bumped on each attempt and the task raises until the counter exceeds
    ``fail_times``.
    """
    if fail_times:
        store = get_store()
        attempts = store.incr(f"jobs:example:attempts:{self.request.id}")
        if attempts <= fail_times:
            raise RuntimeError(f"transient failure {attempts}/{fail_times}")
    return {"message": message, "tenant_id": tenant_id}
