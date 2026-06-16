"""Pydantic schemas for the AI-readiness audit endpoint (P2C-3, GEO-7..GEO-9).

Response-only: the audit is a GET that derives everything from the location's
stored profile, so there is no request body. Shapes mirror the dataclasses in
:mod:`app.geo.ai_readiness` one-for-one.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SignalScoreOut(BaseModel):
    key: str
    label: str
    weight: float
    score: float = Field(..., ge=0, le=100)
    detail: dict
    action: str | None


class RecommendationOut(BaseModel):
    signal: str
    action: str
    priority: Literal["high", "medium", "low"]
    impact_points: float


class AiReadinessOut(BaseModel):
    location_id: UUID
    overall_score: float = Field(..., ge=0, le=100)
    generated_at: datetime
    signals: list[SignalScoreOut]
    recommendations: list[RecommendationOut]
