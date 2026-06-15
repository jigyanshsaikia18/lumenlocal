"""Keyword rank tracking models (P2B-2, DB schema §5 extension).

``KeywordRankSchedule`` — what keyword/device/interval to track for a location.
``KeywordRankResult``   — one scan's map-pack + organic position, for trend charts.

Both are tenant-scoped transitively through ``location_id`` (same RLS pattern as
``geogrid_scans``). Results are indexed on ``(location_id, keyword, device, run_at)``
for the time-series trend queries the chart endpoint will issue.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KeywordRankSchedule(Base):
    __tablename__ = "keyword_rank_schedules"
    __table_args__ = (
        Index("ix_krs_location_active", "location_id", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    location_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    device: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'desktop'")
    )
    interval_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("168")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    last_run_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=False), nullable=True)


class KeywordRankResult(Base):
    __tablename__ = "keyword_rank_results"
    __table_args__ = (
        Index("ix_krr_location_kw_device_run", "location_id", "keyword", "device", "run_at"),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    location_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    device: Mapped[str] = mapped_column(String(20), nullable=False)
    map_pack_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    organic_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), server_default=text("CURRENT_TIMESTAMP")
    )
