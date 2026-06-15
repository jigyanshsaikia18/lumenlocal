"""Pydantic schemas for the usage-cap endpoints (API spec §4, PRD §5 FT-9)."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class UsageMetricOut(BaseModel):
    """Current consumption vs cap for one metered metric (``GET /usage``)."""

    metric: str
    used: int
    limit: int | None  # None = no Super-Admin cap configured for this metric
    remaining: int | None  # None when uncapped
    exceeded: bool
    on_exceed: str | None


class UsageReportResponse(BaseModel):
    """Consumption for a scope across all metered metrics, for the active period."""

    scope_type: str  # tenant | client
    scope_id: UUID
    period_start: date
    metrics: list[UsageMetricOut]


class QuotaOut(BaseModel):
    """A Super-Admin cap row (``GET/PUT /quotas``)."""

    scope_type: str
    scope_id: UUID
    metric: str
    period: str
    limit_value: int
    on_exceed: str


class QuotaListResponse(BaseModel):
    """All caps configured for a scope (``GET /quotas``)."""

    scope_type: str
    scope_id: UUID
    quotas: list[QuotaOut]


class SetQuotaRequest(BaseModel):
    """Body of ``PUT /quotas`` — set/replace a cap for one (scope, metric)."""

    metric: str
    limit_value: int = Field(ge=0)
    period: str = "monthly"
    on_exceed: str = "pause"  # pause | block | alert
