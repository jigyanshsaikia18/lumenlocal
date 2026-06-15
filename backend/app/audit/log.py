"""The audit-log write seam: entry shape, sink Protocol, and implementations.

A writer builds an :class:`AuditLogEntry` and calls :meth:`AuditLogSink.record`.
``record`` only *appends*; the table is immutable (UPDATE/DELETE blocked at the DB
level — see the ``audit_log`` migration), so there is no update/delete path here by
design. The caller owns the surrounding transaction/commit, as elsewhere in the app
(cf. ``SqlAlchemyComplianceEventSink``).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class AuditLogEntry:
    """One ``audit_log`` row: who did what to which entity, with before/after state."""

    tenant_id: UUID
    action: str
    actor_user_id: UUID | None = None
    target_type: str | None = None
    target_id: UUID | None = None
    before: Any | None = None
    after: Any | None = None


class AuditLogSink(Protocol):
    """Appends entries to the immutable audit trail (mock this in tests)."""

    def record(self, entry: AuditLogEntry) -> None: ...


class InMemoryAuditLogSink:
    """Collects entries in a list (tests / dry runs)."""

    def __init__(self) -> None:
        self.entries: list[AuditLogEntry] = []

    def record(self, entry: AuditLogEntry) -> None:
        self.entries.append(entry)


class SqlAlchemyAuditLogSink:
    """Append entries to the append-only ``audit_log`` table (schema §7).

    The runtime ``lumen_app`` role is granted SELECT/INSERT only and a trigger
    rejects UPDATE/DELETE, so this is the *only* mutation the database permits — the
    immutability guarantee holds even if calling code is wrong. RLS scopes rows to
    the request's tenant via ``tenant_id``. The caller owns the transaction/commit.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, entry: AuditLogEntry) -> None:
        self._session.execute(
            text(
                "INSERT INTO audit_log "
                "(tenant_id, actor_user_id, action, target_type, target_id, before, after) "
                "VALUES (:tenant_id, :actor_user_id, :action, :target_type, :target_id, "
                "CAST(:before AS jsonb), CAST(:after AS jsonb))"
            ),
            {
                "tenant_id": entry.tenant_id,
                "actor_user_id": entry.actor_user_id,
                "action": entry.action,
                "target_type": entry.target_type,
                "target_id": entry.target_id,
                "before": None if entry.before is None else json.dumps(entry.before),
                "after": None if entry.after is None else json.dumps(entry.after),
            },
        )
