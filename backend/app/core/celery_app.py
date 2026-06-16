"""Celery application wired to Redis (broker + result backend).

The job framework (``app/jobs``) layers idempotency, per-tenant fairness and
dead-lettering on top of this app via ``TenantTask``. Heavier task modules are
listed in ``include`` (geo-scan landed in P2B-1; sampling, reports follow).
"""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "lumenlocal",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    # Register task modules so the worker discovers them at startup.
    include=[
        "app.jobs.example",
        "app.jobs.geo_scan",
        "app.jobs.geo_ai_scan",
        "app.jobs.token_health",
        "app.jobs.keyword_rank_scan",
        "app.jobs.keyword_rank_dispatch",
    ],
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
    # Periodic tasks (beat schedule). token_health.check runs on a fixed interval
    # and is not tenant-scoped — it sweeps all connections as a platform system job.
    beat_schedule={
        "token-health-check": {
            "task": "token_health.check",
            "schedule": settings.token_health_check_interval_seconds,
        },
        "keyword-rank-dispatch": {
            "task": "keyword_rank.dispatch",
            "schedule": settings.keyword_rank_dispatch_interval_seconds,
        },
    },
)
