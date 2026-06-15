"""``run_keyword_rank_scan`` worker tests (P2B-2).

Mirrors the structure of ``tests/jobs/test_geo_scan.py``:
* Celery runs in eager mode (see tests/jobs/conftest.py — autouse fixture).
* ``tenant_session`` is patched with a fake so no Postgres is needed.
* ``quota_service`` is patched with an in-memory store for metering assertions.

Two concern groups:
1. Happy path — worker records exactly one ``KeywordRankResult`` row and returns
   the correct envelope (both map-pack and organic rank filled in by the mock
   provider).
2. Metering — the ``keyword_rank_scans`` counter is decremented on success; a cap
   hit returns a ``paused`` envelope and does not persist any row.
"""
from __future__ import annotations

import contextlib
from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.jobs import keyword_rank_scan as krs_module
from app.quotas.service import (
    METRIC_KEYWORD_RANK_SCANS,
    SCOPE_TENANT,
    QuotaService,
)
from tests.quotas.fakes import FakeQuotaStore

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

TENANT_1 = "11111111-1111-1111-1111-111111111111"


class _FakeSession:
    """Minimal stand-in for a SQLAlchemy Session scoped to one tenant."""

    def __init__(self, location):
        self._location = location
        self.added = []
        self.executed = []

    def get(self, model, pk):
        return self._location

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()

    def execute(self, stmt, params=None):
        self.executed.append((stmt, params))
        return SimpleNamespace(fetchall=lambda: [], scalar_one_or_none=lambda: None)


@pytest.fixture
def fake_tenant_session(monkeypatch):
    """Patch krs_module.tenant_session to yield a configurable fake session."""
    holder: dict = {}

    def _install(location, store: FakeQuotaStore | None = None):
        session = _FakeSession(location)
        holder["session"] = session
        _store = store if store is not None else FakeQuotaStore()

        @contextlib.contextmanager
        def _fake(tenant_id):
            holder["tenant_id"] = tenant_id
            yield session

        monkeypatch.setattr(krs_module, "tenant_session", _fake)
        monkeypatch.setattr(
            krs_module, "quota_service", lambda _s: QuotaService(_store)
        )
        holder["store"] = _store
        return holder

    return _install


def _location(lat=40.0, lon=-75.0):
    return SimpleNamespace(id=uuid4(), latitude=lat, longitude=lon)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

def test_scan_persists_one_result_row(fake_tenant_session):
    loc = _location()
    holder = fake_tenant_session(loc)

    result = krs_module.run_keyword_rank_scan.delay(
        tenant_id=TENANT_1,
        location_id=str(loc.id),
        keyword="plumber near me",
        device="desktop",
    ).get()

    assert result["status"] == "ok"
    assert result["keyword"] == "plumber near me"
    assert result["device"] == "desktop"

    # Exactly one KeywordRankResult row added.
    assert len(holder["session"].added) == 1
    row = holder["session"].added[0]
    assert row.keyword == "plumber near me"
    assert row.device == "desktop"
    assert row.location_id == loc.id
    # Mock provider returns deterministic values — just ensure the types are right.
    assert row.map_pack_rank is None or isinstance(row.map_pack_rank, int)
    assert row.organic_rank is None or isinstance(row.organic_rank, int)


def test_result_id_in_envelope(fake_tenant_session):
    loc = _location()
    holder = fake_tenant_session(loc)

    result = krs_module.run_keyword_rank_scan.delay(
        tenant_id=TENANT_1,
        location_id=str(loc.id),
        keyword="dentist",
        device="mobile",
    ).get()

    row = holder["session"].added[0]
    assert result["result_id"] == str(row.id)


def test_schedule_last_run_at_updated(fake_tenant_session):
    """The UPDATE to keyword_rank_schedules is issued after a successful scan."""
    loc = _location()
    holder = fake_tenant_session(loc)

    krs_module.run_keyword_rank_scan.delay(
        tenant_id=TENANT_1,
        location_id=str(loc.id),
        keyword="pizza",
        device="desktop",
    ).get()

    # At least one execute call should be for the schedule UPDATE.
    sql_texts = [str(stmt) for stmt, _ in holder["session"].executed]
    assert any("keyword_rank_schedules" in t for t in sql_texts)


# ---------------------------------------------------------------------------
# Metering tests
# ---------------------------------------------------------------------------

def test_metering_decrements_counter(fake_tenant_session):
    """A successful scan consumes exactly one keyword_rank_scans credit."""
    store = FakeQuotaStore()
    loc = _location()
    fake_tenant_session(loc, store)

    krs_module.run_keyword_rank_scan.delay(
        tenant_id=TENANT_1,
        location_id=str(loc.id),
        keyword="coffee shop",
        device="desktop",
    ).get()

    period = date.today().replace(day=1)
    used = store.get_used(SCOPE_TENANT, UUID(TENANT_1), METRIC_KEYWORD_RANK_SCANS, period)
    assert used == 1


def test_metering_multiple_scans_accumulate(fake_tenant_session):
    """Credits accumulate across multiple scans in the same period."""
    store = FakeQuotaStore()
    loc = _location()
    fake_tenant_session(loc, store)

    for kw in ["pizza", "dentist", "plumber"]:
        krs_module.run_keyword_rank_scan.delay(
            tenant_id=TENANT_1,
            location_id=str(loc.id),
            keyword=kw,
            device="desktop",
        ).get()

    period = date.today().replace(day=1)
    used = store.get_used(SCOPE_TENANT, UUID(TENANT_1), METRIC_KEYWORD_RANK_SCANS, period)
    assert used == 3


def test_quota_cap_pauses_gracefully(fake_tenant_session):
    """When the cap is hit the worker returns paused and records no row."""
    from app.quotas.service import ON_EXCEED_PAUSE, Quota

    store = FakeQuotaStore()
    # Set cap to 0 so the first attempt is refused.
    store.quotas[(SCOPE_TENANT, UUID(TENANT_1), METRIC_KEYWORD_RANK_SCANS)] = Quota(
        scope_type=SCOPE_TENANT,
        scope_id=UUID(TENANT_1),
        metric=METRIC_KEYWORD_RANK_SCANS,
        period="monthly",
        limit_value=0,
        on_exceed=ON_EXCEED_PAUSE,
    )
    loc = _location()
    holder = fake_tenant_session(loc, store)

    result = krs_module.run_keyword_rank_scan.delay(
        tenant_id=TENANT_1,
        location_id=str(loc.id),
        keyword="pizza",
        device="desktop",
    ).get()

    assert result["status"] == "paused"
    assert result["reason"] == "quota_exceeded"
    # No rows should have been persisted.
    assert len(holder["session"].added) == 0


# ---------------------------------------------------------------------------
# Error path tests
# ---------------------------------------------------------------------------

def test_missing_location_raises(fake_tenant_session):
    fake_tenant_session(None)

    with pytest.raises(ValueError, match="not found"):
        krs_module.run_keyword_rank_scan.delay(
            tenant_id=TENANT_1,
            location_id=str(uuid4()),
            keyword="pizza",
            device="desktop",
        ).get()


def test_location_without_coordinates_raises(fake_tenant_session):
    fake_tenant_session(_location(lat=None, lon=None))

    with pytest.raises(ValueError, match="coordinates"):
        krs_module.run_keyword_rank_scan.delay(
            tenant_id=TENANT_1,
            location_id=str(uuid4()),
            keyword="pizza",
            device="desktop",
        ).get()
