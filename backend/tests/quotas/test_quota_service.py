"""Unit tests for QuotaService — the decision/consumption logic (no Postgres).

Covers the FT-9 contract: hard caps stop consumption at the limit and alert;
uncapped metrics are tracked but never blocked; the soft ``alert`` cap lets work
through but warns; and ``usage_report`` reflects consumption vs caps.
"""
from datetime import date
from uuid import uuid4

import pytest

from app.alerts import SEVERITY_CRITICAL, SEVERITY_WARNING, InMemoryAlertSink
from app.quotas.service import (
    METERED_METRICS,
    METRIC_GEOGRID_SCANS,
    METRIC_GOOGLE_API_CALLS,
    METRIC_LLM_CREDITS,
    ON_EXCEED_ALERT,
    ON_EXCEED_BLOCK,
    ON_EXCEED_PAUSE,
    SCOPE_CLIENT,
    SCOPE_TENANT,
    QuotaService,
)
from tests.quotas.fakes import FakeQuotaStore

FIXED_DAY = date(2026, 6, 15)
PERIOD_START = date(2026, 6, 1)


@pytest.fixture
def env():
    store = FakeQuotaStore()
    alerts = InMemoryAlertSink()
    service = QuotaService(store, alerts=alerts, clock=lambda: FIXED_DAY)
    return store, alerts, service


def test_period_start_is_month_start(env):
    _, _, service = env
    assert service.period_start() == PERIOD_START


def test_uncapped_metric_is_tracked_but_never_blocked(env):
    store, alerts, service = env
    scope = uuid4()
    for expected in (1, 2, 3):
        d = service.consume(SCOPE_TENANT, scope, METRIC_GEOGRID_SCANS)
        assert d.allowed is True
        assert d.exceeded is False
        assert d.limit is None
        assert d.used == expected
    assert alerts.alerts == []  # nothing to warn about without a cap


def test_hard_cap_stops_at_limit_and_alerts(env):
    store, alerts, service = env
    scope = uuid4()
    store.set_quota(SCOPE_TENANT, scope, METRIC_GEOGRID_SCANS, 2, "monthly", ON_EXCEED_PAUSE)

    assert service.consume(SCOPE_TENANT, scope, METRIC_GEOGRID_SCANS).allowed is True
    assert service.consume(SCOPE_TENANT, scope, METRIC_GEOGRID_SCANS).allowed is True

    # Third consume is refused: not allowed, nothing consumed beyond the cap.
    d = service.consume(SCOPE_TENANT, scope, METRIC_GEOGRID_SCANS)
    assert d.allowed is False
    assert d.exceeded is True
    assert d.used == 2  # held at the cap
    assert d.limit == 2
    assert store.get_used(SCOPE_TENANT, scope, METRIC_GEOGRID_SCANS, PERIOD_START) == 2

    # Exactly one critical alert for the cap hit.
    assert len(alerts.alerts) == 1
    assert alerts.alerts[0].kind == "quota.exceeded"
    assert alerts.alerts[0].severity == SEVERITY_CRITICAL


def test_block_mode_refuses_like_pause(env):
    store, alerts, service = env
    scope = uuid4()
    store.set_quota(SCOPE_CLIENT, scope, METRIC_GOOGLE_API_CALLS, 1, "monthly", ON_EXCEED_BLOCK)
    assert service.consume(SCOPE_CLIENT, scope, METRIC_GOOGLE_API_CALLS).allowed is True
    d = service.consume(SCOPE_CLIENT, scope, METRIC_GOOGLE_API_CALLS)
    assert d.allowed is False
    assert d.on_exceed == ON_EXCEED_BLOCK
    assert alerts.alerts[0].severity == SEVERITY_CRITICAL


def test_soft_alert_cap_allows_but_warns(env):
    store, alerts, service = env
    scope = uuid4()
    store.set_quota(SCOPE_TENANT, scope, METRIC_LLM_CREDITS, 2, "monthly", ON_EXCEED_ALERT)

    assert service.consume(SCOPE_TENANT, scope, METRIC_LLM_CREDITS).allowed is True  # used=1
    assert service.consume(SCOPE_TENANT, scope, METRIC_LLM_CREDITS).allowed is True  # used=2
    assert alerts.alerts == []  # at the cap, not yet over

    d = service.consume(SCOPE_TENANT, scope, METRIC_LLM_CREDITS)  # used=3 > 2
    assert d.allowed is True  # soft cap never blocks
    assert d.exceeded is True
    assert d.used == 3
    assert len(alerts.alerts) == 1
    assert alerts.alerts[0].severity == SEVERITY_WARNING


def test_consume_amount_greater_than_one(env):
    store, _, service = env
    scope = uuid4()
    store.set_quota(SCOPE_TENANT, scope, METRIC_LLM_CREDITS, 10, "monthly", ON_EXCEED_PAUSE)
    assert service.consume(SCOPE_TENANT, scope, METRIC_LLM_CREDITS, amount=7).used == 7
    # 7 + 5 > 10 → refused, stays at 7.
    d = service.consume(SCOPE_TENANT, scope, METRIC_LLM_CREDITS, amount=5)
    assert d.allowed is False
    assert d.used == 7
    # 7 + 3 == 10 → allowed exactly to the cap.
    assert service.consume(SCOPE_TENANT, scope, METRIC_LLM_CREDITS, amount=3).used == 10


def test_remaining_headroom(env):
    store, _, service = env
    scope = uuid4()
    store.set_quota(SCOPE_TENANT, scope, METRIC_GEOGRID_SCANS, 5, "monthly", ON_EXCEED_PAUSE)
    service.consume(SCOPE_TENANT, scope, METRIC_GEOGRID_SCANS, amount=2)
    assert service.remaining(SCOPE_TENANT, scope, METRIC_GEOGRID_SCANS) == 3
    assert service.remaining(SCOPE_TENANT, scope, METRIC_GOOGLE_API_CALLS) is None  # uncapped


def test_usage_report_covers_all_metrics(env):
    store, _, service = env
    scope = uuid4()
    store.set_quota(SCOPE_TENANT, scope, METRIC_GEOGRID_SCANS, 3, "monthly", ON_EXCEED_PAUSE)
    service.consume(SCOPE_TENANT, scope, METRIC_GEOGRID_SCANS)
    service.consume(SCOPE_TENANT, scope, METRIC_GOOGLE_API_CALLS)  # uncapped

    report = {d.metric: d for d in service.usage_report(SCOPE_TENANT, scope)}
    assert set(report) == set(METERED_METRICS)  # every metered metric appears
    assert report[METRIC_GEOGRID_SCANS].used == 1
    assert report[METRIC_GEOGRID_SCANS].limit == 3
    assert report[METRIC_GOOGLE_API_CALLS].used == 1
    assert report[METRIC_GOOGLE_API_CALLS].limit is None
    assert report[METRIC_LLM_CREDITS].used == 0  # untouched metric still reported


def test_usage_report_is_read_only(env):
    store, _, service = env
    scope = uuid4()
    service.usage_report(SCOPE_TENANT, scope)
    assert store.counters == {}  # reporting consumes nothing


@pytest.mark.parametrize(
    "kwargs",
    [
        {"metric": "not_a_metric", "limit_value": 10},
        {"metric": METRIC_GEOGRID_SCANS, "limit_value": -1},
        {"metric": METRIC_GEOGRID_SCANS, "limit_value": 10, "on_exceed": "explode"},
    ],
)
def test_set_quota_rejects_bad_input(env, kwargs):
    _, _, service = env
    with pytest.raises(ValueError):
        service.set_quota(SCOPE_TENANT, uuid4(), **kwargs)


def test_set_quota_rejects_bad_scope_type(env):
    _, _, service = env
    with pytest.raises(ValueError):
        service.set_quota("galaxy", uuid4(), METRIC_GEOGRID_SCANS, 10)
