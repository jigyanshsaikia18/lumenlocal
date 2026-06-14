"""``TenantTask`` — the base class that makes every job retryable, idempotent,
tenant-fair, and dead-letter-backed.

Tasks opt in by ``base=TenantTask``. The contract for a tenant-scoped task:

* pass the owning tenant as a keyword argument ``tenant_id`` (str/UUID). Tasks
  without one are treated as system tasks and skip the fairness gate.
* optionally pass ``idempotency_key=`` to make the submission run-at-most-once.
  This is framework metadata, popped before the task body runs, so task
  functions never need a parameter for it.

What the base adds around the task body (``__call__``):

1. **Idempotency** — a fresh submission claims its key; a duplicate is skipped
   and returns a ``"duplicate"`` envelope. Retries of the *same* task keep the
   claim and are never mistaken for duplicates.
2. **Fairness** — acquire a per-tenant in-flight slot or yield the worker by
   re-queuing, so no single tenant can monopolise the pool.
3. **Retries** — exponential backoff with jitter via the Celery decorator
   options exported here; the slot is released on every attempt so the counter
   stays balanced across retries.
4. **Dead-lettering** — once retries are exhausted, ``on_failure`` parks the
   attempt on the DLQ and frees the idempotency claim.
"""
from __future__ import annotations

import logging
from typing import Any

from celery import Task

from app.core.config import settings
from app.jobs import dead_letter, fairness, idempotency
from app.jobs.store import get_store

logger = logging.getLogger("app.jobs")

# Shared Celery options for tenant tasks: autoretry on any error with jittered
# exponential backoff, capped by config. Spread onto @celery_app.task(...).
TENANT_TASK_OPTIONS: dict[str, Any] = {
    "base": None,  # filled in by example.py / callers with TenantTask
    "bind": True,
    # The framework injects metadata kwargs (idempotency_key) that the task body
    # never declares; __call__ strips them before the body runs. Celery's signature
    # typing check runs in apply_async *before* that, so it must be off or it would
    # reject the metadata kwarg as "unexpected". (tenant_id is a real, declared arg.)
    "typing": False,
    "autoretry_for": (Exception,),
    "max_retries": settings.jobs_max_retries,
    "retry_backoff": True,
    "retry_backoff_max": settings.jobs_retry_backoff_max,
    "retry_jitter": True,
    "acks_late": True,
}


class TenantTask(Task):
    """Celery task base adding idempotency, per-tenant fairness and dead-lettering."""

    # Reliability defaults; a worker dying mid-task re-queues rather than drops.
    acks_late = True
    reject_on_worker_lost = True

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _tenant_id(kwargs: dict[str, Any]) -> str | None:
        tid = kwargs.get("tenant_id")
        return str(tid) if tid is not None else None

    def _idempotency_key(self, kwargs: dict[str, Any]) -> str | None:
        # Prefer an explicit kwarg; fall back to an apply_async header so callers
        # who don't want the value in the signature can still set it.
        key = kwargs.get("idempotency_key")
        if key is None:
            headers = getattr(self.request, "headers", None) or {}
            key = headers.get("idempotency_key")
        return str(key) if key is not None else None

    # -- execution wrapper -------------------------------------------------
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        store = get_store()
        tenant_id = self._tenant_id(kwargs)
        idem_key = self._idempotency_key(kwargs)
        first_attempt = self.request.retries == 0

        # idempotency_key is framework metadata — strip it so the task body, which
        # never declares it, isn't handed an unexpected argument.
        kwargs.pop("idempotency_key", None)

        # 1. Idempotency — only gate fresh submissions, not our own retries.
        if idem_key and first_attempt and not idempotency.claim(
            store, idem_key, settings.jobs_idempotency_ttl_seconds
        ):
            existing = idempotency.state(store, idem_key)
            logger.info(
                "jobs.duplicate task=%s idempotency_key=%s state=%s",
                self.name, idem_key, existing,
            )
            return {"status": "duplicate", "idempotency_key": idem_key, "state": existing}

        # 2. Fairness — take an in-flight slot, or yield the worker to other tenants.
        acquired = False
        if tenant_id is not None:
            acquired = fairness.acquire(
                store,
                tenant_id,
                settings.jobs_tenant_concurrency,
                settings.jobs_inflight_ttl_seconds,
            )
            if not acquired and not self.request.is_eager:
                # Re-queue behind the tenant's other work. Eager mode (tests) has
                # no broker to re-queue onto, so there we just proceed.
                logger.info("jobs.yield task=%s tenant=%s at_capacity", self.name, tenant_id)
                raise self.retry(countdown=settings.jobs_fairness_retry_delay)

        # 3. Run the body, always releasing the slot we took.
        try:
            result = super().__call__(*args, **kwargs)
        except Exception:
            if acquired:
                fairness.release(store, tenant_id)  # type: ignore[arg-type]
            raise  # autoretry / on_failure take it from here

        if acquired:
            fairness.release(store, tenant_id)  # type: ignore[arg-type]
        if idem_key:
            idempotency.mark_done(store, idem_key, settings.jobs_idempotency_ttl_seconds)
        return result

    # -- terminal failure --------------------------------------------------
    def on_failure(
        self,
        exc: BaseException,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        """Retries are spent: dead-letter the attempt and free the idem claim."""
        store = get_store()
        dead_letter.record(
            store,
            task_name=self.name,
            task_id=task_id,
            tenant_id=self._tenant_id(kwargs),
            args=args,
            kwargs=kwargs,
            exc=exc,
        )
        idem_key = self._idempotency_key(kwargs)
        if idem_key:
            # Drop the claim so the work can be resubmitted once the cause is fixed.
            idempotency.release(store, idem_key)
        logger.error("jobs.dead_letter task=%s id=%s exc=%s", self.name, task_id, exc)
        super().on_failure(exc, task_id, args, kwargs, einfo)
