"""P1C-2: the audit-log write seam — entry shape + in-memory sink."""
from uuid import uuid4

from app.audit.log import AuditLogEntry, AuditLogSink, InMemoryAuditLogSink


def test_in_memory_sink_satisfies_protocol_and_records():
    sink: AuditLogSink = InMemoryAuditLogSink()
    entry = AuditLogEntry(tenant_id=uuid4(), action="entitlement.override.set")
    sink.record(entry)
    assert sink.entries == [entry]


def test_entry_optional_fields_default_to_none():
    entry = AuditLogEntry(tenant_id=uuid4(), action="x")
    assert entry.actor_user_id is None
    assert entry.target_type is None
    assert entry.target_id is None
    assert entry.before is None
    assert entry.after is None
