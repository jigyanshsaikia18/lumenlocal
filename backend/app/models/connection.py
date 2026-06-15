"""``GbpConnection`` — an OAuth binding between a client and Google (DB schema §4).

One row per GBP connection (self-serve or agency-proxy). The raw OAuth token
**never** lands here: only ``token_ref`` — an opaque pointer into the secrets
vault — is persisted (CLAUDE.md hard rule; see ``app.core.vault``). ``scopes`` and
``expires_at`` are non-secret metadata kept for the connection-health monitor
(PRD §6 ON-6). Scoped transitively to a tenant through ``client_id`` (RLS), like
``geogrid_scans`` is through ``location_id``.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, Index, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GbpConnection(Base):
    __tablename__ = "gbp_connections"
    __table_args__ = (Index("ix_gbp_connections_client_id", "client_id"),)

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    client_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    # self_serve (client connects) | agency_proxy (agency-on-behalf) — PRD §6.
    connect_method: Mapped[str] = mapped_column(String(20), nullable=False)
    # Opaque vault pointer — NEVER the raw token (CLAUDE.md hard rule).
    token_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    token_status: Mapped[str] = mapped_column(String(20), server_default=text("'healthy'"))
    expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=False), nullable=True
    )
