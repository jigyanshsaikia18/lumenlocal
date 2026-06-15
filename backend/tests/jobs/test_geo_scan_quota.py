"""P1C-4 acceptance (worker half): a metered geo-grid scan stops at its cap.

Runs ``run_geogrid_scan`` through the real job framework in eager mode with the
``tenant_session`` boundary and the quota seam faked (no Postgres). Proves the
FT-9 behaviour for a metered worker:

* scans up to the cap succeed and increment ``usage_counters``;
* the next scan **pauses gracefully** — returns a ``paused`` envelope, runs no
  scan, and does *not* raise (so it is neither retried nor dead-lettered); and
* an operator alert fires when the cap is hit.
"""
import contextlib
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.alerts import InMemoryAlertSink
from app.jobs import geo_scan
from app.quotas.service import (
    METRIC_GEOGRID_SCANS,
    ON_EXCEED_PAUSE,
    SCOPE_TENANT,
    QuotaService,
)
from tests.quotas.fakes import FakeQuotaStore

TENANT = "11111111-1111-1111-1111-111111111111"
CAP = 2


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
def metered_env(monkeypatch):
    """Wire an eager worker with a shared (capped) quota store + alert sink."""
    from uuid import UUID

    store = FakeQuotaStore()
    store.set_quota(SCOPE_TENANT, UUID(TENANT), METRIC_GEOGRID_SCANS, CAP, "monthly", ON_EXCEED_PAUSE)
    alerts = InMemoryAlertSink()
    location = SimpleNamespace(id=uuid4(), latitude=40.0, longitude=-75.0)
    session = _FakeSession(location)

    @contextlib.contextmanager
    def _fake_session(tenant_id):
        yield session

    monkeypatch.setattr(geo_scan, "tenant_session", _fake_session)
    # One service instance over one store/sink so consumption accumulates and
    # alerts are observable across submissions.
    service = QuotaService(store, alerts=alerts)
    monkeypatch.setattr(geo_scan, "quota_service", lambda _session: service)

    return SimpleNamespace(store=store, alerts=alerts, session=session, location=location)


def _run(location_id):
    return geo_scan.run_geogrid_scan.delay(
        tenant_id=TENANT,
        location_id=str(location_id),
        search_term="pizza",
        grid_dimensions=3,
        radius_miles=5.0,
    ).get()


def test_scans_stop_at_cap_and_alert(metered_env):
    from uuid import UUID

    loc_id = metered_env.location.id

    # The first CAP scans run and persist.
    for i in range(CAP):
        res = _run(loc_id)
        assert res["status"] == "ok", f"scan {i} should run within the cap"
    assert len(metered_env.session.added) == CAP
    assert metered_env.alerts.alerts == []  # no alert while under the cap

    # Counter reflects exactly the consumption so far.
    used = metered_env.store.get_used(
        SCOPE_TENANT, UUID(TENANT), METRIC_GEOGRID_SCANS, QuotaService(metered_env.store).period_start()
    )
    assert used == CAP

    # The next scan is over the cap: it pauses gracefully, runs no scan, no raise.
    res = _run(loc_id)
    assert res["status"] == "paused"
    assert res["reason"] == "quota_exceeded"
    assert res["metric"] == METRIC_GEOGRID_SCANS
    assert res["used"] == CAP
    assert res["limit"] == CAP
    assert len(metered_env.session.added) == CAP  # still CAP — nothing new persisted

    # Exactly one operator alert fired for the cap hit.
    assert len(metered_env.alerts.alerts) == 1
    alert = metered_env.alerts.alerts[0]
    assert alert.kind == "quota.exceeded"
    assert alert.context["metric"] == METRIC_GEOGRID_SCANS


def test_paused_scan_is_not_dead_lettered(metered_env):
    """A quota pause must not error-storm: no exception ⇒ no dead-letter row."""
    from app.jobs import dead_letter
    from app.jobs.store import get_store

    loc_id = metered_env.location.id
    for _ in range(CAP + 3):  # well past the cap
        res = _run(loc_id)
        assert res["status"] in ("ok", "paused")

    parked = dead_letter.read(get_store())
    assert parked == []  # graceful pause never dead-letters
