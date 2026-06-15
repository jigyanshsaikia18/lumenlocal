"""Super-Admin usage caps + consumption tracking (schema §3, PRD §5 FT-9).

Two tables, both scope-keyed (``scope_type`` = ``tenant`` / ``client``, ``scope_id``
the matching id) rather than carrying a plain ``tenant_id``:

* ``usage_quotas`` — the hard monthly caps a Super-Admin sets on the expensive,
  metered operations (``google_api_calls`` / ``geogrid_scans`` / ``ai_scans`` /
  ``llm_credits``). ``on_exceed`` selects what happens at the cap
  (``pause`` / ``alert`` / ``block``).
* ``usage_counters`` — current-period consumption, **incremented transactionally by
  workers** (schema §8). One row per (scope, metric, ``period_start``); the
  migration's unique constraint over those columns is what makes the worker's
  atomic upsert-increment safe under concurrency.

Quota checks read the current-period counter before enqueuing/running expensive
jobs; the resolution logic lives in ``app.quotas``. Like the entitlement override
tables (see ``c4e1a7b2f9d3``), these are scope-keyed and not covered by the P1A-2
tenant RLS policies — tenant-scoping of these tables is a documented follow-up.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import BigInteger, Date, Index, String, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UsageQuota(Base):
    """A Super-Admin hard cap for one (scope, metric) per period (schema §3)."""

    __tablename__ = "usage_quotas"
    __table_args__ = (
        Index("ix_usage_quotas_scope_id", "scope_id"),
        # One active cap per (scope, metric, period) — the resolver reads at most one.
        UniqueConstraint(
            "scope_type", "scope_id", "metric", "period",
            name="uq_usage_quotas_scope_metric_period",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)  # tenant / client
    scope_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    metric: Mapped[str] = mapped_column(String(40), nullable=False)
    period: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'monthly'")
    )
    limit_value: Mapped[int] = mapped_column(BigInteger, nullable=False)  # hard cap
    # pause / alert / block — what the metered op does once the cap is hit.
    on_exceed: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pause'")
    )


class UsageCounter(Base):
    """Consumption for one (scope, metric) in one period — incremented by workers."""

    __tablename__ = "usage_counters"
    __table_args__ = (
        Index("ix_usage_counters_scope_id", "scope_id"),
        Index("ix_usage_counters_metric", "metric"),
        Index("ix_usage_counters_period_start", "period_start"),
        # The atomic upsert-increment in SqlAlchemyQuotaStore targets this key.
        UniqueConstraint(
            "scope_type", "scope_id", "metric", "period_start",
            name="uq_usage_counters_scope_metric_period",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    metric: Mapped[str] = mapped_column(String(40), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    used_value: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    # Touch time of the last increment — useful for "last activity" displays.
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), server_default=text("CURRENT_TIMESTAMP")
    )
