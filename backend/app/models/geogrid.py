"""``GeogridScan`` — one classic spatial-ranking scan (DB schema §5).

A scan samples the business's map rank across an ``N × N`` coordinate grid around a
location and stores the per-node results (``matrix_results``) plus the rolled-up
Share of Local Voice (``solv``). Written by the ``run_geogrid_scan`` worker
(``app.jobs.geo_scan``). Tenant-scoped transitively through ``location_id`` (RLS).
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GeogridScan(Base):
    __tablename__ = "geogrid_scans"
    # Trend queries read a location's scans newest-first (schema §8).
    __table_args__ = (Index("ix_geogrid_scans_location_run_at", "location_id", "run_at"),)

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    location_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    search_term: Mapped[str] = mapped_column(String(255), nullable=False)
    grid_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    # Coord → rank + competitors, one entry per node.
    matrix_results: Mapped[list] = mapped_column(JSONB, nullable=False)
    solv: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    run_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), server_default=text("CURRENT_TIMESTAMP")
    )
