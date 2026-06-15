"""Pydantic schemas for keyword rank tracking endpoints (P2B-2)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


DeviceType = Literal["desktop", "mobile"]


class KeywordRankScheduleCreate(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=255)
    device: DeviceType = "desktop"
    interval_hours: int = Field(168, ge=1, le=8760, description="Hours between scheduled runs")


class KeywordRankScheduleOut(BaseModel):
    id: UUID
    location_id: UUID
    keyword: str
    device: str
    interval_hours: int
    is_active: bool
    last_run_at: datetime | None

    model_config = {"from_attributes": True}


class KeywordRankScanTrigger(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=255)
    device: DeviceType = "desktop"


class KeywordRankResultOut(BaseModel):
    id: UUID
    location_id: UUID
    keyword: str
    device: str
    map_pack_rank: int | None
    organic_rank: int | None
    run_at: datetime

    model_config = {"from_attributes": True}


class KeywordRankScanEnqueued(BaseModel):
    status: str
    task_id: str
    location_id: UUID
    keyword: str
    device: str
