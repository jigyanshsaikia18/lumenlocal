"""Fixtures for rank tracking tests.

Applies the same eager-mode + clean-store setup as ``tests/jobs/conftest.py``
so ``run_keyword_rank_scan.delay(...).get()`` executes synchronously in-process
without a broker.
"""
import pytest

from app.core.celery_app import celery_app
from app.jobs.store import reset_memory_store


@pytest.fixture(autouse=True)
def eager_mode():
    prev_eager = celery_app.conf.task_always_eager
    prev_prop = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False
    reset_memory_store()
    yield
    celery_app.conf.task_always_eager = prev_eager
    celery_app.conf.task_eager_propagates = prev_prop
