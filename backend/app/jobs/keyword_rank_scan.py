"""``run_keyword_rank_scan`` — keyword rank tracking worker (P2B-2).

Queries the mock search provider for a location + keyword + device combination,
records one ``keyword_rank_results`` row (map-pack rank + organic rank), and
updates the owning schedule's ``last_run_at`` so the dispatch sweep knows when
the next run is due.

Metering: consumes one ``keyword_rank_scans`` credit against the tenant cap before
doing any work (same pattern as ``run_geogrid_scan``).  A quota hit returns a
``paused`` envelope without retrying — the cap service fires the operator alert.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.core.celery_app import celery_app
from app.db.session import tenant_session
from app.jobs.base import TENANT_TASK_OPTIONS, TenantTask
from app.models.location import Location
from app.models.rank import KeywordRankResult
from app.quotas.service import (
    METRIC_KEYWORD_RANK_SCANS,
    SCOPE_TENANT,
    QuotaService,
    SqlAlchemyQuotaStore,
)
from app.rank.mock_provider import mock_ranks

_OPTS: dict[str, Any] = {**TENANT_TASK_OPTIONS, "base": TenantTask}


def quota_service(session: Any) -> QuotaService:
    """Build the metering service over the worker's tenant session.

    A seam so tests can monkeypatch without Postgres.
    """
    return QuotaService(SqlAlchemyQuotaStore(session))


@celery_app.task(**_OPTS)
def run_keyword_rank_scan(
    self,
    *,
    tenant_id: str,
    location_id: str,
    keyword: str,
    device: str = "desktop",
) -> dict[str, Any]:
    """Scan one keyword/device combination and persist the result.

    Args:
        tenant_id: Owning tenant — routes fairness and scopes RLS.
        location_id: The location to scan (must have lat/lon).
        keyword: The search keyword to track.
        device: ``'desktop'`` or ``'mobile'`` (changes provider context).

    Returns:
        ``{"status": "ok", "result_id", "location_id", "keyword", "device",
          "map_pack_rank", "organic_rank"}`` on success, or
        ``{"status": "paused", "reason": "quota_exceeded", ...}`` when the cap
        is hit (the op does not retry — the quota service alerts instead).

    Raises:
        ValueError: location unknown to this tenant or missing coordinates.
    """
    with tenant_session(tenant_id) as session:
        decision = quota_service(session).consume(
            SCOPE_TENANT, UUID(str(tenant_id)), METRIC_KEYWORD_RANK_SCANS
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
            raise ValueError(f"location {location_id} not found for tenant {tenant_id}")
        if location.latitude is None or location.longitude is None:
            raise ValueError(f"location {location_id} has no coordinates")

        map_pack, organic = mock_ranks(
            lat=float(location.latitude),
            lon=float(location.longitude),
            keyword=keyword,
            device=device,
        )

        result = KeywordRankResult(
            location_id=location.id,
            keyword=keyword,
            device=device,
            map_pack_rank=map_pack,
            organic_rank=organic,
        )
        session.add(result)
        session.flush()  # populate result.id

        # Mark the schedule as just-run so the dispatch sweep skips it until the
        # next interval.  Uses a plain UPDATE instead of an ORM load to avoid a
        # second round-trip; the schedule row may not exist for ad-hoc triggers.
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        session.execute(
            text(
                "UPDATE keyword_rank_schedules SET last_run_at = :now "
                "WHERE location_id = :lid AND keyword = :kw AND device = :dev "
                "AND is_active = TRUE"
            ),
            {"now": now_utc, "lid": location_id, "kw": keyword, "dev": device},
        )

        result_id = str(result.id)

    return {
        "status": "ok",
        "result_id": result_id,
        "location_id": location_id,
        "keyword": keyword,
        "device": device,
        "map_pack_rank": map_pack,
        "organic_rank": organic,
    }
