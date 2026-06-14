"""Celery application wired to Redis (broker + result backend).

Scaffold only — task modules are added in later phases (geo-scan, sampling, reports).
"""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "lumenlocal",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)
