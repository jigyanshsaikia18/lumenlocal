"""Fixtures for the job-framework tests.

These tests are pure-unit: they run Celery in *eager* mode (no broker) and the
framework's store factory swaps in the process-local in-memory store, so no
Redis or Postgres is required (matching tests/test_health.py).
"""
import pytest

from app.core.celery_app import celery_app
from app.jobs.store import InMemoryStore, reset_memory_store


@pytest.fixture(autouse=True)
def eager_mode():
    """Run tasks synchronously in-process and start each test with a clean store."""
    prev_eager = celery_app.conf.task_always_eager
    prev_prop = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    # Keep propagation OFF so eager mode runs the autoretry loop synchronously
    # (a transient failure re-executes) instead of surfacing the first Retry. The
    # final outcome is stored on the EagerResult and re-raised by .get().
    celery_app.conf.task_eager_propagates = False
    reset_memory_store()
    yield
    celery_app.conf.task_always_eager = prev_eager
    celery_app.conf.task_eager_propagates = prev_prop


@pytest.fixture
def store() -> InMemoryStore:
    """A fresh in-memory store for direct unit tests of the framework modules."""
    return InMemoryStore()
