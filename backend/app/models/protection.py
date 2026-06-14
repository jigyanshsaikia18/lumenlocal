"""``ProfileChangeEvent`` — profile-protection monitoring + audit trail (schema §7).

One row per detected change to a monitored profile field: the ``old_value`` (from
the locked baseline) vs the ``new_value`` (detected live on Google), the assigned
``severity``, and the ``action_taken`` by the bounded-revert policy
(``alerted`` / ``reverted`` / ``ignored`` — see ``app.protection.revert``). It is
the proof trail that a critical change was caught and handled (PRD §7).

Append-only: the migration grants the app role SELECT/INSERT only. Tenant-scoped
transitively through ``location_id`` (RLS), exactly like ``geogrid_scans``.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, Index, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProfileChangeEvent(Base):
    __tablename__ = "profile_change_events"
    # Trend/audit queries read a location's events newest-first (schema §8).
    __table_args__ = (
        Index("ix_profile_change_events_location_detected_at", "location_id", "detected_at"),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    location_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    # Which of the 20+ monitored fields moved (name, primary_category, phone, …).
    field: Mapped[str] = mapped_column(String(60), nullable=True)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # from baseline
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # detected live
    # low / medium / high (e.g. map-pin move past threshold = high).
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # alerted / reverted / ignored — what the bounded-revert policy did.
    action_taken: Mapped[str | None] = mapped_column(String(20), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), server_default=text("CURRENT_TIMESTAMP")
    )
