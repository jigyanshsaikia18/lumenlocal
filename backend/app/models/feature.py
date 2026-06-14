"""Entitlement tables (DB schema §3) — the feature-toggle engine's source of truth.

``Feature`` is the registry of toggleable capabilities; the three override tables
(``plan_features`` / ``client_features`` / ``location_features``) hold per-scope
on/off states. The resolved set across them — *most specific wins:
location > client > plan > default* — is computed by ``app.entitlements``.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Feature(Base):
    """Registry of toggleable capabilities (PRD §5 FT-1)."""

    __tablename__ = "features"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    dependencies: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    default_state: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )


class _FeatureOverride:
    """Shared shape of the three per-scope override tables (schema §3).

    ``scope_id`` is a plan_id / client_id / location_id depending on the table;
    it carries no FK because the referent differs per table. ``index=True`` gives
    each concrete table its own ``ix_<table>_scope_id`` index.
    """

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    scope_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    feature_key: Mapped[str] = mapped_column(
        String(80), ForeignKey("features.key"), nullable=False
    )
    state: Mapped[bool] = mapped_column(Boolean, nullable=False)
    set_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    set_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), server_default=text("CURRENT_TIMESTAMP")
    )


class PlanFeature(_FeatureOverride, Base):
    """Plan-level override (``scope_id`` = plan_id)."""

    __tablename__ = "plan_features"


class ClientFeature(_FeatureOverride, Base):
    """Client-level override (``scope_id`` = client_id)."""

    __tablename__ = "client_features"


class LocationFeature(_FeatureOverride, Base):
    """Location-level override (``scope_id`` = location_id)."""

    __tablename__ = "location_features"
