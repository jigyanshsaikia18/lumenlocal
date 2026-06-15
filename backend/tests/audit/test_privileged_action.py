"""P1E-3: privileged action writes an audit row (unit test, no Postgres needed).

Shows that the ``EntitlementAdminService`` — one representative of the "privileged
action" class — appends an ``AuditLogEntry`` to the sink on every feature toggle.

The InMemoryAuditLogSink is used in place of the real SQLAlchemy sink so this
suite runs without a database connection.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.audit.log import AuditLogEntry, InMemoryAuditLogSink
from app.entitlements.admin import ACTION_SET_OVERRIDE, EntitlementAdminService
from app.entitlements.repository import EntitlementService
from app.security.context import RequestContext, RoleAssignment
from tests.entitlements.fakes import FakeEntitlementBackend, feat

TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CLIENT = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _build(features=None):
    feats = features or [feat("geogrid", default=True)]
    backend = FakeEntitlementBackend(feats)
    sink = InMemoryAuditLogSink()
    service = EntitlementService(backend)
    admin = EntitlementAdminService(backend, service, sink)
    return admin, sink


def _ctx(tenant_id: UUID = TENANT) -> RequestContext:
    return RequestContext(
        user_id=uuid4(),
        tenant_id=tenant_id,
        roles=(RoleAssignment(role="agency_admin"),),
    )


def test_feature_toggle_writes_exactly_one_audit_row():
    """A single set_client_override call produces one AuditLogEntry."""
    admin, sink = _build()
    admin.set_client_override(_ctx(), CLIENT, "geogrid", False)
    assert len(sink.entries) == 1


def test_audit_row_has_correct_who_what_target():
    """The entry records actor, action key, tenant, and target entity."""
    admin, sink = _build()
    ctx = _ctx()
    admin.set_client_override(ctx, CLIENT, "geogrid", False)
    entry: AuditLogEntry = sink.entries[0]
    assert entry.action == ACTION_SET_OVERRIDE
    assert entry.tenant_id == TENANT
    assert entry.actor_user_id == ctx.user_id
    assert entry.target_type == "client"
    assert entry.target_id == CLIENT


def test_audit_row_captures_before_and_after_state():
    """before/after carry the feature key and its old/new boolean state."""
    admin, sink = _build()
    admin.set_client_override(_ctx(), CLIENT, "geogrid", False)
    entry = sink.entries[0]
    # No prior override → before.state is None (was inherited from plan default).
    assert entry.before == {"feature_key": "geogrid", "state": None}
    assert entry.after == {"feature_key": "geogrid", "state": False}


def test_second_toggle_captures_previous_override_as_before():
    """Once an override exists, the next toggle's before.state reflects it."""
    admin, sink = _build()
    ctx = _ctx()
    admin.set_client_override(ctx, CLIENT, "geogrid", False)
    admin.set_client_override(ctx, CLIENT, "geogrid", True)

    assert len(sink.entries) == 2
    # First write: no prior override.
    assert sink.entries[0].before == {"feature_key": "geogrid", "state": None}
    # Second write: previous override was False.
    assert sink.entries[1].before == {"feature_key": "geogrid", "state": False}
    assert sink.entries[1].after == {"feature_key": "geogrid", "state": True}


def test_rejected_toggle_writes_no_audit_row():
    """A toggle refused due to missing dependency must not produce an audit entry."""
    admin, sink = _build(
        [feat("review_inbox", default=False), feat("ai_writer", deps=("review_inbox",))]
    )
    with pytest.raises(Exception):
        admin.set_client_override(_ctx(), CLIENT, "ai_writer", True)
    assert sink.entries == []
