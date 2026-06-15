"""Multi-location command-center endpoint (API spec §5, PRD §7 D-3, P1E-2).

``GET /clients/{client_id}/command-center``
  Returns roll-up KPIs + per-location summaries for a client's full portfolio.
  Gated by ``dashboard_multi_location`` (entitlement step 3 of §12 chain).
  Min role: ``analyst`` (``locations.read`` capability).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.entitlements.gateway import require_feature
from app.locations.service import LocationService
from app.schemas.locations import (
    CommandCenterOut,
    LocationKPIsOut,
    LocationSummaryOut,
)
from app.security.context import RequestContext

router = APIRouter(tags=["locations"])

MULTI_LOCATION_FEATURE = "dashboard_multi_location"


def get_location_service(db: Session = Depends(get_db)) -> LocationService:
    """Request-scoped location service (overridden in tests — no DB needed)."""
    return LocationService(db)


@router.get(
    "/clients/{client_id}/command-center",
    response_model=CommandCenterOut,
)
def get_command_center(
    client_id: UUID,
    ctx: RequestContext = Depends(
        require_feature(
            MULTI_LOCATION_FEATURE,
            "locations.read",
            client_param="client_id",
        )
    ),
    service: LocationService = Depends(get_location_service),
) -> CommandCenterOut:
    """Roll-up KPIs + per-location summaries for the multi-location map view.

    Entitlement-gated: ``dashboard_multi_location`` off → ``403 feature_disabled``.
    All 5 middleware steps (§12) fire before this handler executes.
    """
    data = service.get_command_center(ctx.tenant_id, client_id)
    return CommandCenterOut(
        client_id=data.client_id,
        total_locations=data.total_locations,
        rollup=LocationKPIsOut(
            views=data.rollup.views,
            calls=data.rollup.calls,
            directions=data.rollup.directions,
            website_clicks=data.rollup.website_clicks,
        ),
        locations=[
            LocationSummaryOut(
                id=loc.id,
                name=loc.name,
                latitude=loc.latitude,
                longitude=loc.longitude,
                health_score=loc.health_score,
                kpis=LocationKPIsOut(
                    views=loc.kpis.views,
                    calls=loc.kpis.calls,
                    directions=loc.kpis.directions,
                    website_clicks=loc.kpis.website_clicks,
                ),
            )
            for loc in data.locations
        ],
    )
