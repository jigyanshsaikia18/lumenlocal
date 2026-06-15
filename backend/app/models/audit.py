"""The platform-wide immutable audit log (DB schema §7, RBAC-5).

``AuditLog`` is the append-only record of every privileged action: who did what to
which entity, with the before/after state. Entitlement toggles (P1C-2), and later
every other privileged write, append one row here.

Immutability is enforced at the **database** level, not by convention (CLAUDE.md
hard rule; PRD §11.1 item 4): the runtime ``lumen_app`` role is granted only
SELECT/INSERT, and a trigger rejects UPDATE/DELETE even for the table owner. See the
``audit_log`` migration. The read API over this table is P1E-3; this model + the
``app.audit`` sink are what writers use.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """One immutable, append-only privileged-action record (schema §7)."""

    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # Who performed the action (NULL only for system actors).
    actor_user_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # The capability/action key, e.g. "entitlement.override.set".
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    # The entity acted on: target_type a coarse kind ("client" / "location"), target_id its id.
    target_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # State before/after the change (NULL where not applicable).
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), server_default=text("CURRENT_TIMESTAMP"), index=True
    )
