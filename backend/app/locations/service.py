"""Location service — command-center aggregation (P1E-2, PRD §7 D-3).

``compute_rollup`` is a pure function (no I/O) so it can be unit-tested without
a database or HTTP layer.  ``LocationService.get_command_center`` reads locations
from Postgres and delegates to it; tests override the service dependency rather
than the DB so the pure aggregation logic is tested in isolation.

KPI fields (views, calls, directions, website_clicks) are stored in
``profile_data_live`` JSONB while the GBP Performance API integration lands in
Phase 2 — the service falls back gracefully to 0 for any missing field.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session


@dataclass
class LocationKPIs:
    views: int = 0
    calls: int = 0
    directions: int = 0
    website_clicks: int = 0


@dataclass
class LocationSummary:
    id: UUID
    name: str
    latitude: float | None
    longitude: float | None
    health_score: int
    kpis: LocationKPIs


@dataclass
class CommandCenterData:
    client_id: UUID
    total_locations: int
    rollup: LocationKPIs
    locations: list[LocationSummary]


def compute_rollup(locations: list[LocationSummary]) -> LocationKPIs:
    """Sum KPIs across all locations — pure, database-free, testable."""
    return LocationKPIs(
        views=sum(s.kpis.views for s in locations),
        calls=sum(s.kpis.calls for s in locations),
        directions=sum(s.kpis.directions for s in locations),
        website_clicks=sum(s.kpis.website_clicks for s in locations),
    )


class LocationService:
    """Aggregates per-location data for the multi-location command center."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_command_center(self, tenant_id: UUID, client_id: UUID) -> CommandCenterData:
        from app.models.location import Location  # avoid circular at module level

        rows = (
            self._db.query(Location)
            .filter(
                Location.tenant_id == tenant_id,
                Location.client_id == client_id,
            )
            .all()
        )
        summaries = [
            LocationSummary(
                id=row.id,
                name=row.profile_data_live.get("name", "Unnamed location"),
                latitude=float(row.latitude) if row.latitude is not None else None,
                longitude=float(row.longitude) if row.longitude is not None else None,
                health_score=int(row.profile_data_live.get("health_score", 0)),
                kpis=LocationKPIs(
                    views=int(row.profile_data_live.get("views", 0)),
                    calls=int(row.profile_data_live.get("calls", 0)),
                    directions=int(row.profile_data_live.get("directions", 0)),
                    website_clicks=int(row.profile_data_live.get("website_clicks", 0)),
                ),
            )
            for row in rows
        ]
        rollup = compute_rollup(summaries)
        return CommandCenterData(
            client_id=client_id,
            total_locations=len(summaries),
            rollup=rollup,
            locations=summaries,
        )
