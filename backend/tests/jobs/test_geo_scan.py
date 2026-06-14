"""run_geogrid_scan worker (P2B-1) through the full job framework, no Postgres.

These run in eager mode (see tests/jobs/conftest.py) and monkeypatch the
``tenant_session`` boundary with a fake so the task's real body executes —
grid math, mock query, SoLV, and the persistence call — without a database.
The migration/model give the actual table; here we prove the worker logic.
"""
import contextlib
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.jobs import geo_scan


class _FakeSession:
    """Minimal stand-in for a SQLAlchemy Session scoped to one tenant."""

    def __init__(self, location):
        self._location = location
        self.added = []

    def get(self, model, pk):
        return self._location

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        # Mimic the DB assigning a primary key on flush.
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()


@pytest.fixture
def fake_tenant_session(monkeypatch):
    """Patch geo_scan.tenant_session to yield a configurable fake session."""

    holder = {}

    def _install(location):
        session = _FakeSession(location)
        holder["session"] = session

        @contextlib.contextmanager
        def _fake(tenant_id):
            holder["tenant_id"] = tenant_id
            yield session

        monkeypatch.setattr(geo_scan, "tenant_session", _fake)
        return holder

    return _install


def _location(lat=40.0, lon=-75.0):
    return SimpleNamespace(id=uuid4(), latitude=lat, longitude=lon)


def test_scan_persists_one_row_and_returns_envelope(fake_tenant_session):
    loc = _location()
    holder = fake_tenant_session(loc)

    result = geo_scan.run_geogrid_scan.delay(
        tenant_id="t1",
        location_id=str(loc.id),
        search_term="pizza",
        grid_dimensions=5,
        radius_miles=5.0,
    ).get()

    # Exactly one geogrid_scans row was added, carrying the computed matrix + SoLV.
    assert len(holder["session"].added) == 1
    scan = holder["session"].added[0]
    assert scan.grid_dimensions == 5
    assert scan.search_term == "pizza"
    assert len(scan.matrix_results) == 25
    assert 0.0 <= float(scan.solv) <= 100.0

    # The session was scoped to the caller's tenant.
    assert holder["tenant_id"] == "t1"

    # Envelope mirrors the persisted row.
    assert result["node_count"] == 25
    assert result["solv"] == float(scan.solv)
    assert result["scan_id"] == str(scan.id)


def test_missing_location_dead_letters(fake_tenant_session):
    fake_tenant_session(None)  # session.get returns None → ValueError in the body

    res = geo_scan.run_geogrid_scan.delay(
        tenant_id="t9",
        location_id=str(uuid4()),
        search_term="pizza",
        grid_dimensions=3,
        radius_miles=5.0,
    )
    with pytest.raises(ValueError):
        res.get()

    from app.jobs import dead_letter
    from app.jobs.store import get_store

    parked = dead_letter.read(get_store())
    assert len(parked) == 1
    assert parked[0]["task_name"].endswith("geo_scan.run_geogrid_scan")
    assert parked[0]["tenant_id"] == "t9"


def test_location_without_coordinates_errors(fake_tenant_session):
    fake_tenant_session(_location(lat=None, lon=None))

    res = geo_scan.run_geogrid_scan.delay(
        tenant_id="t1",
        location_id=str(uuid4()),
        search_term="pizza",
        grid_dimensions=3,
        radius_miles=5.0,
    )
    with pytest.raises(ValueError):
        res.get()
