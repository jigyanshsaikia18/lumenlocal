"""Celery application wired to Redis (broker + result backend).

The job framework (``app/jobs``) layers idempotency, per-tenant fairness and
dead-lettering on top of this app via ``TenantTask``. Heavier task modules
(geo-scan, sampling, reports) are added in later phases and listed in ``include``.
"""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "lumenlocal",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    # Register task modules so the worker discovers them at startup.
    include=["app.jobs.example"],
)

celery_app.conf.update(
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
    task_default_queue=settings.jobs_default_queue,
    # Fairness foundations (02_Technical_Architecture §8): a worker pulls one task
    # at a time and only acks after completion, so it can't greedily prefetch one
    # tenant's backlog and the cooperative gate in app/jobs/fairness.py stays honest.
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
