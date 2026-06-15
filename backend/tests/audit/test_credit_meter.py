"""P1E-3: CreditMeter scaffold — quota enforcement + audit entry in one call.

Tests that ``CreditMeter.consume`` atomically decides whether a metered op may
proceed AND writes a ``credit.consumed`` audit entry when it does.  All
dependencies are in-memory; no database or network needed.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from app.audit.log import InMemoryAuditLogSink
from app.quotas.meter import ACTION_CREDIT_CONSUMED, CreditMeter
from app.quotas.service import (
    METRIC_GEOGRID_SCANS,
    SCOPE_TENANT,
    ON_EXCEED_PAUSE,
    Quota,
    QuotaService,
)
from tests.quotas.fakes import FakeQuotaStore

TENANT = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _meter(*, quota_limit: int | None = None) -> tuple[CreditMeter, InMemoryAuditLogSink]:
    store = FakeQuotaStore()
    if quota_limit is not None:
        store.set_quota(
            SCOPE_TENANT, TENANT, METRIC_GEOGRID_SCANS,
            quota_limit, "monthly", ON_EXCEED_PAUSE,
        )
    svc = QuotaService(store, clock=lambda: date(2026, 6, 1))
    sink = InMemoryAuditLogSink()
    return CreditMeter(svc, sink), sink


def test_allowed_op_emits_audit_entry():
    meter, sink = _meter()
    result = meter.consume(
        tenant_id=TENANT,
        scope_id=TENANT,
        metric=METRIC_GEOGRID_SCANS,
    )
    assert result.allowed is True
    assert len(sink.entries) == 1
    entry = sink.entries[0]
    assert entry.action == ACTION_CREDIT_CONSUMED
    assert entry.tenant_id == TENANT
    assert entry.after["metric"] == METRIC_GEOGRID_SCANS
    assert entry.after["amount"] == 1
    assert entry.after["used"] == 1


def test_blocked_op_does_not_emit_audit_entry():
    """Hard cap refusal must not write to the audit log."""
    meter, sink = _meter(quota_limit=0)
    result = meter.consume(
        tenant_id=TENANT,
        scope_id=TENANT,
        metric=METRIC_GEOGRID_SCANS,
    )
    assert result.allowed is False
    assert sink.entries == []


def test_audit_entry_carries_actor_and_target():
    meter, sink = _meter()
    actor = uuid4()
    target = uuid4()
    meter.consume(
        tenant_id=TENANT,
        scope_id=TENANT,
        metric=METRIC_GEOGRID_SCANS,
        actor_user_id=actor,
        target_type="location",
        target_id=target,
    )
    entry = sink.entries[0]
    assert entry.actor_user_id == actor
    assert entry.target_type == "location"
    assert entry.target_id == target


def test_audit_entry_records_limit_and_scope():
    meter, sink = _meter(quota_limit=100)
    meter.consume(tenant_id=TENANT, scope_id=TENANT, metric=METRIC_GEOGRID_SCANS)
    after = sink.entries[0].after
    assert after["limit"] == 100
    assert after["scope_type"] == SCOPE_TENANT
    assert after["scope_id"] == str(TENANT)
