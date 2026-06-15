"""Platform-wide audit trail (RBAC-5, DB schema §7 ``audit_log``).

Privileged actions append an immutable record of *who did what to which entity*,
with before/after state. The write seam mirrors how ``app.compliance`` and
``app.protection`` record their trails: a pure :class:`AuditLogEntry`, an
injectable :class:`AuditLogSink` Protocol, an in-memory implementation for tests,
and a SQLAlchemy one that appends to the append-only table.
"""
from app.audit.log import (
    AuditLogEntry,
    AuditLogSink,
    InMemoryAuditLogSink,
    SqlAlchemyAuditLogSink,
)

__all__ = [
    "AuditLogEntry",
    "AuditLogSink",
    "InMemoryAuditLogSink",
    "SqlAlchemyAuditLogSink",
]
