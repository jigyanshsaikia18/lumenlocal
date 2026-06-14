"""Shared fakes for the protection suite — no DB, no Google, no real clock.

A revert is an *external write*, so the service is wired to a **real**
``PolicyGateway`` (over the real engine + an in-memory event sink) — exactly the
production composition minus Postgres — plus a spy ``ProfileWriter`` so a test can
assert whether Google was written, and an in-memory recorder for the audit trail.
``_SpyGateway`` wraps the real gateway only to count how many times ``guard`` ran,
proving the revert actually passed through the Policy Engine.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.compliance import (
    ComplianceEventData,
    DEFAULT_RULESET,
    ExternalWrite,
    PolicyComplianceEngine,
    PolicyGateway,
)
from app.protection import (
    InMemoryChangeEventRecorder,
    InMemoryRevertRateLimiter,
    ProtectionService,
)


class SpyWriter:
    """Records every restore_field call instead of touching Google."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def restore_field(self, *, location_id, field, value) -> None:
        self.calls.append({"location_id": location_id, "field": field, "value": value})


class MemorySink:
    """In-memory ComplianceEventSink (mirrors tests/compliance/test_gateway.py)."""

    def __init__(self) -> None:
        self.events: list[ComplianceEventData] = []

    def record(self, event: ComplianceEventData) -> None:
        self.events.append(event)


class SpyGateway:
    """Wrap a real PolicyGateway, counting guard() calls (still really evaluates)."""

    def __init__(self, inner: PolicyGateway) -> None:
        self._inner = inner
        self.guard_calls: list[ExternalWrite] = []

    def guard(self, action: ExternalWrite):
        self.guard_calls.append(action)
        return self._inner.guard(action)


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def sink():
    return MemorySink()


@pytest.fixture
def real_gateway(sink, tenant_id):
    engine = PolicyComplianceEngine(DEFAULT_RULESET)
    return PolicyGateway(engine, sink, tenant_id=tenant_id)


@pytest.fixture
def gateway(real_gateway):
    """Spy over the real gateway so tests can assert it was consulted."""
    return SpyGateway(real_gateway)


@pytest.fixture
def writer():
    return SpyWriter()


@pytest.fixture
def recorder():
    return InMemoryChangeEventRecorder()


@pytest.fixture
def rate_limiter():
    return InMemoryRevertRateLimiter()


@pytest.fixture
def service(gateway, writer, rate_limiter, recorder):
    return ProtectionService(
        gateway=gateway,
        writer=writer,
        rate_limiter=rate_limiter,
        recorder=recorder,
    )


def make_location(
    *,
    revert_mode: str,
    locked: dict | None = None,
    live: dict | None = None,
):
    """A minimal stand-in for the SQLAlchemy Location the service reads."""
    return SimpleNamespace(
        id=uuid4(),
        revert_mode=revert_mode,
        profile_data_locked=locked if locked is not None else {},
        profile_data_live=live if live is not None else {},
    )
