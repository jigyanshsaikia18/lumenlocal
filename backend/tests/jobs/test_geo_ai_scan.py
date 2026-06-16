"""run_geo_ai_scan worker (P2C-2) through the job framework, no Postgres.

Eager mode (tests/jobs/conftest.py); the ``tenant_session`` boundary is faked so
the task's real body runs — grid math, the offline AI provider, SAIV, and the
persistence call — without a database. Mirrors tests/jobs/test_geo_scan.py.
"""
import contextlib
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.jobs import geo_ai_scan
from app.quotas.service import QuotaService
from tests.quotas.fakes import FakeQuotaStore


class _FakeSession:
    def __init__(self, location):
        self._location = location
        self.added = []

    def get(self, model, pk):
        return self._location

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()


@pytest.fixture
def fake_tenant_session(monkeypatch):
    """Patch geo_ai_scan.tenant_session to yield a configurable fake session.

    Installs an uncapped in-memory quota service so the metering gate lets the
    scan proceed; the cap itself is exercised in test_geo_ai_scan_quota.py.
    """
    holder = {}

    def _install(location):
        session = _FakeSession(location)
        holder["session"] = session

        @contextlib.contextmanager
        def _fake(tenant_id):
            holder["tenant_id"] = tenant_id
            yield session

        monkeypatch.setattr(geo_ai_scan, "tenant_session", _fake)
        monkeypatch.setattr(
            geo_ai_scan, "quota_service", lambda _session: QuotaService(FakeQuotaStore())
        )
        return holder

    return _install


TENANT_1 = "11111111-1111-1111-1111-111111111111"
TENANT_9 = "99999999-9999-9999-9999-999999999999"


def _location(lat=40.0, lon=-75.0, name="Riverside Bistro"):
    return SimpleNamespace(
        id=uuid4(), latitude=lat, longitude=lon, profile_data_live={"name": name}
    )


def test_scan_persists_one_row_and_returns_envelope(fake_tenant_session):
    loc = _location()
    holder = fake_tenant_session(loc)

    result = geo_ai_scan.run_geo_ai_scan.delay(
        tenant_id=TENANT_1,
        location_id=str(loc.id),
        prompt="best bistro near me",
        provider="chatgpt",
        grid_dimensions=5,
        radius_miles=5.0,
        sample_runs=2,
    ).get()

    # Exactly one geo_ai_scans row, carrying the computed matrix + SAIV + sources.
    assert len(holder["session"].added) == 1
    scan = holder["session"].added[0]
    assert scan.provider == "chatgpt"
    assert scan.prompt == "best bistro near me"
    assert scan.grid_dimensions == 5
    assert scan.sample_runs == 2
    assert len(scan.matrix_results) == 25
    assert all(len(node["runs"]) == 2 for node in scan.matrix_results)
    assert 0.0 <= float(scan.saiv) <= 100.0
    assert isinstance(scan.cited_sources, list)

    assert holder["tenant_id"] == TENANT_1

    # Envelope mirrors the persisted row.
    assert result["status"] == "ok"
    assert result["provider"] == "chatgpt"
    assert result["node_count"] == 25
    assert result["sample_runs"] == 2
    assert result["saiv"] == float(scan.saiv)
    assert result["cited_source_count"] == len(scan.cited_sources)
    assert result["scan_id"] == str(scan.id)


def test_unknown_provider_dead_letters(fake_tenant_session):
    loc = _location()
    fake_tenant_session(loc)

    res = geo_ai_scan.run_geo_ai_scan.delay(
        tenant_id=TENANT_1,
        location_id=str(loc.id),
        prompt="best bistro near me",
        provider="bing_chat",  # not a known surface
        grid_dimensions=3,
        radius_miles=5.0,
    )
    with pytest.raises(ValueError):
        res.get()


def test_missing_location_dead_letters(fake_tenant_session):
    fake_tenant_session(None)  # session.get returns None → ValueError in the body

    res = geo_ai_scan.run_geo_ai_scan.delay(
        tenant_id=TENANT_9,
        location_id=str(uuid4()),
        prompt="best bistro near me",
        provider="ai_overviews",
        grid_dimensions=3,
        radius_miles=5.0,
    )
    with pytest.raises(ValueError):
        res.get()

    from app.jobs import dead_letter
    from app.jobs.store import get_store

    parked = dead_letter.read(get_store())
    assert len(parked) == 1
    assert parked[0]["task_name"].endswith("geo_ai_scan.run_geo_ai_scan")
    assert parked[0]["tenant_id"] == TENANT_9


def test_location_without_coordinates_errors(fake_tenant_session):
    fake_tenant_session(_location(lat=None, lon=None))

    res = geo_ai_scan.run_geo_ai_scan.delay(
        tenant_id=TENANT_1,
        location_id=str(uuid4()),
        prompt="best bistro near me",
        provider="gemini",
        grid_dimensions=3,
        radius_miles=5.0,
    )
    with pytest.raises(ValueError):
        res.get()
