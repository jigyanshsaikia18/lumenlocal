"""``Location`` — a client's physical outlet (DB schema §4).

A location is the geo-grid centroid (its ``latitude``/``longitude``) and the unit
profile protection operates on. Tenant-scoped via ``tenant_id`` (RLS) and owned by
a ``client``.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        Index("ix_locations_tenant_id", "tenant_id"),
        Index("ix_locations_client_id", "client_id"),
        Index("ix_locations_google_place_id", "google_place_id"),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    client_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    google_place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # NUMERIC(9,6): ~0.1 m resolution, enough for a geo-grid centroid.
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    profile_data_live: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    profile_data_locked: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_protected: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    # Bounded, configurable — NOT silent timer-writes (CLAUDE.md compliance rule).
    revert_mode: Mapped[str] = mapped_column(String(20), server_default=text("'alert_only'"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), server_default=text("CURRENT_TIMESTAMP")
    )
