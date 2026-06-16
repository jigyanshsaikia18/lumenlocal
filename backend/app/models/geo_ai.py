"""``GeoAiScan`` — one AI-search visibility scan (DB schema §5, flagship).

The GEO analogue of :class:`~app.models.geogrid.GeogridScan`: instead of a map
rank per node it stores, per node, the business's mention/prominence across the
repeated sample runs (``matrix_results``), the rolled-up AI-Search Visibility
(``saiv``), and the third-party sources the AI cited (``cited_sources``). Written
by the ``run_geo_ai_scan`` worker (``app.jobs.geo_ai_scan``). Tenant-scoped
transitively through ``location_id`` (RLS), exactly like ``geogrid_scans``.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GeoAiScan(Base):
    __tablename__ = "geo_ai_scans"
    # Trend queries read a location's scans newest-first (schema §8).
    __table_args__ = (Index("ix_geo_ai_scans_location_run_at", "location_id", "run_at"),)

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    location_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    # One of ai_overviews / ai_mode / gemini / chatgpt / perplexity / grok
    # (matches app.geo.ai.records.Provider values).
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt: Mapped[str] = mapped_column(String(500), nullable=False)
    # Geo-grid-for-AI sampling: N → N×N nodes. Nullable (a scan may sample a
    # single point rather than a grid).
    grid_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sample_runs: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    # Coord → mention/prominence per run, one entry per node.
    matrix_results: Mapped[list] = mapped_column(JSONB, nullable=False)
    saiv: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    cited_sources: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    run_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), server_default=text("CURRENT_TIMESTAMP")
    )
