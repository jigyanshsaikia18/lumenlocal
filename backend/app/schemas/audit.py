"""Pydantic schemas for the audit log read API (P1E-3, DB schema §7)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogEntryOut(BaseModel):
    """One immutable ``audit_log`` row as returned by the read API."""

    id: UUID
    tenant_id: UUID
    actor_user_id: UUID | None = None
    action: str
    target_type: str | None = None
    target_id: UUID | None = None
    before: dict | None = None
    after: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogPage(BaseModel):
    """Paginated response for ``GET /audit-log``."""

    entries: list[AuditLogEntryOut]
    total: int
    skip: int
    limit: int
