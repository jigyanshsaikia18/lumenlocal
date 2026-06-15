"""Pydantic schemas for location-level dashboard endpoints (API spec §5, PRD §7 D-3).

``CommandCenterOut`` is returned by ``GET /clients/{client_id}/command-center``
(P1E-2). Response bodies never carry ``tenant_id``; scoping is resolved from the
JWT by the middleware chain (API spec §12).
"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LocationKPIsOut(BaseModel):
    """Rolled-up or per-location GBP Performance KPIs (30-day window)."""

    views: int = Field(ge=0)
    calls: int = Field(ge=0)
    directions: int = Field(ge=0)
    website_clicks: int = Field(ge=0)


class LocationSummaryOut(BaseModel):
    """One location as seen by the command-center map (PRD §7 D-3)."""

    model_config = ConfigDict(from_attributes=False)

    id: UUID
    name: str
    latitude: float | None
    longitude: float | None
    health_score: int = Field(ge=0, le=100)
    kpis: LocationKPIsOut


class CommandCenterOut(BaseModel):
    """Response for ``GET /clients/{client_id}/command-center``.

    ``rollup`` is the arithmetic sum of KPIs across *all* client locations,
    regardless of any filter applied client-side.  ``locations`` is the full
    per-location list; filtering is done by the frontend so the rollup stays
    consistent with the server truth.
    """

    client_id: UUID
    total_locations: int = Field(ge=0)
    rollup: LocationKPIsOut
    locations: list[LocationSummaryOut]
