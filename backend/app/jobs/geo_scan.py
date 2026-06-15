"""``run_geogrid_scan`` — the classic geo-grid rank-tracking worker (P2B-1).

Given a location, a keyword, a grid size and a radius, this task lays out the
coordinate grid, queries each node (mocked until P2B-2) and persists a single
``geogrid_scans`` row with the per-node ``matrix_results`` and the rolled-up SoLV.

It rides the P2A-1 job framework (``base=TenantTask``): tenant-fair, idempotent,
retried and dead-lettered. All persistence goes through ``tenant_session`` so the
read of the location and the write of the scan are constrained to the owning
tenant by row-level security, not convention.

Geo-grid scanning is a **metered** operation (PRD §5 FT-9): before doing any work
the task consumes one ``geogrid_scans`` unit against the tenant's Super-Admin cap.
If the cap is hit the task **pauses gracefully** — it returns a ``paused`` envelope
and lets the quota service fire the operator alert, rather than raising (which would
autoretry and dead-letter, i.e. error-storm). The counter increment and the scan
write share the one ``tenant_session`` transaction, so usage is consistent with work.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.celery_app import celery_app
from app.db.session import tenant_session
from app.geo.scan import build_matrix
from app.jobs.base import TENANT_TASK_OPTIONS, TenantTask
from app.models.geogrid import GeogridScan
from app.models.location import Location
from app.quotas.service import (
    METRIC_GEOGRID_SCANS,
    SCOPE_TENANT,
    QuotaService,
    SqlAlchemyQuotaStore,
)

_OPTS: dict[str, Any] = {**TENANT_TASK_OPTIONS, "base": TenantTask}


def quota_service(session: Any) -> QuotaService:
    """Build the metering service over the worker's tenant session.

    A seam so tests can drive the cap without Postgres (monkeypatch this name);
    in production it wraps the live ``usage_quotas`` / ``usage_counters`` tables.
    """
    return QuotaService(SqlAlchemyQuotaStore(session))


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
        On success ``{"status": "ok", "scan_id", "location_id", "node_count", "solv"}``;
        when the tenant's ``geogrid_scans`` cap is hit,
        ``{"status": "paused", "reason": "quota_exceeded", "metric", "used", "limit"}``
        (no scan is run and the op does not retry).

    Raises:
        ValueError: if the location is unknown to this tenant or has no coordinates.
    """
    with tenant_session(tenant_id) as session:
        # Step 4 of the §12 chain for a metered job: consume against the cap first.
        # A hit pauses gracefully (alert fired by the service); we do not raise, so
        # the framework neither retries nor dead-letters this — no error-storm.
        decision = quota_service(session).consume(
            SCOPE_TENANT, UUID(str(tenant_id)), METRIC_GEOGRID_SCANS
        )
        if not decision.allowed:
            return {
                "status": "paused",
                "reason": "quota_exceeded",
                "metric": decision.metric,
                "location_id": location_id,
                "used": decision.used,
                "limit": decision.limit,
            }

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
        "status": "ok",
        "scan_id": scan_id,
        "location_id": location_id,
        "node_count": len(matrix),
        "solv": solv,
    }
