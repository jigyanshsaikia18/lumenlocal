"""``run_geogrid_scan`` — the classic geo-grid rank-tracking worker (P2B-1).

Given a location, a keyword, a grid size and a radius, this task lays out the
coordinate grid, queries each node (mocked until P2B-2) and persists a single
``geogrid_scans`` row with the per-node ``matrix_results`` and the rolled-up SoLV.

It rides the P2A-1 job framework (``base=TenantTask``): tenant-fair, idempotent,
retried and dead-lettered. All persistence goes through ``tenant_session`` so the
read of the location and the write of the scan are constrained to the owning
tenant by row-level security, not convention.
"""
from __future__ import annotations

from typing import Any

from app.core.celery_app import celery_app
from app.db.session import tenant_session
from app.geo.scan import build_matrix
from app.jobs.base import TENANT_TASK_OPTIONS, TenantTask
from app.models.geogrid import GeogridScan
from app.models.location import Location

_OPTS: dict[str, Any] = {**TENANT_TASK_OPTIONS, "base": TenantTask}


@celery_app.task(**_OPTS)
def run_geogrid_scan(  # noqa: ANN001 - `self` injected by bind=True
    self,
    *,
    tenant_id: str,
    location_id: str,
    search_term: str,
    grid_dimensions: int,
    radius_miles: float,
) -> dict[str, Any]:
    """Run a geo-grid scan for one location and persist the result.

    Args:
        tenant_id: Owning tenant (routes fairness + scopes RLS).
        location_id: The location whose centroid (lat/lon) anchors the grid.
        search_term: Keyword being tracked.
        grid_dimensions: Grid size ``N`` → ``N × N`` nodes.
        radius_miles: Distance from the centroid to the grid edge.

    Returns:
        ``{"scan_id", "location_id", "node_count", "solv"}``.

    Raises:
        ValueError: if the location is unknown to this tenant or has no coordinates.
    """
    with tenant_session(tenant_id) as session:
        location = session.get(Location, location_id)
        if location is None:
            # RLS hides other tenants' locations, so "not found" is the right signal.
            raise ValueError(f"location {location_id} not found for tenant {tenant_id}")
        if location.latitude is None or location.longitude is None:
            raise ValueError(f"location {location_id} has no coordinates to scan")

        matrix, solv = build_matrix(
            lat=float(location.latitude),
            lon=float(location.longitude),
            radius_miles=radius_miles,
            dimensions=grid_dimensions,
            search_term=search_term,
        )

        scan = GeogridScan(
            location_id=location.id,
            search_term=search_term,
            grid_dimensions=grid_dimensions,
            matrix_results=matrix,
            solv=solv,
        )
        session.add(scan)
        session.flush()  # populate scan.id before the session closes
        scan_id = str(scan.id)

    return {
        "scan_id": scan_id,
        "location_id": location_id,
        "node_count": len(matrix),
        "solv": solv,
    }
