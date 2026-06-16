"""Keyword rank tracking endpoints (API spec §6, P2B-2).

Endpoints:
  POST /locations/{location_id}/keyword-rank-schedules   — add a tracked keyword
  GET  /locations/{location_id}/keyword-rank-schedules   — list tracked keywords
  POST /locations/{location_id}/keyword-rank-scans       — trigger an ad-hoc scan
  GET  /locations/{location_id}/keyword-rank-results     — trend history

All are gated by the ``keyword_rank`` feature flag and require at minimum the
``geogrid.run`` / ``geogrid.read`` capabilities (reusing the rank-tracking
capability bundle until a dedicated one is added in RBAC).  Min role: analyst+.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.session import get_db
from app.entitlements.gateway import require_feature
from app.jobs.keyword_rank_scan import run_keyword_rank_scan
from app.models.location import Location
from app.models.rank import KeywordRankResult, KeywordRankSchedule
from app.schemas.rank import (
    KeywordRankResultOut,
    KeywordRankScanEnqueued,
    KeywordRankScanTrigger,
    KeywordRankScheduleCreate,
    KeywordRankScheduleOut,
)
from app.security.context import RequestContext

router = APIRouter(tags=["rank_tracking"])

RANK_FEATURE = "keyword_rank"


def _assert_location_in_tenant(db: Session, location_id: UUID, ctx: RequestContext) -> None:
    """Guard tenant isolation: 404 unless ``location_id`` belongs to the caller's tenant.

    These handlers run on the privileged (RLS-bypassing) ``get_db`` session and the
    rank tables are scoped to a tenant only transitively through ``location_id``, so
    a bare ``WHERE location_id = …`` would otherwise read/write across tenants. We
    verify ownership explicitly — ``ctx.tenant_id`` is load-bearing for isolation —
    and 404 (not 403) so a foreign location is indistinguishable from a missing one.
    """
    owned = db.scalar(
        select(Location.id).where(
            Location.id == location_id, Location.tenant_id == ctx.tenant_id
        )
    )
    if owned is None:
        raise APIError(
            404, "not_found", "Location not found", {"location_id": str(location_id)}
        )


# --------------------------------------------------------------------------- #
# Schedules                                                                    #
# --------------------------------------------------------------------------- #

@router.post(
    "/locations/{location_id}/keyword-rank-schedules",
    response_model=KeywordRankScheduleOut,
    status_code=201,
)
def create_keyword_rank_schedule(
    location_id: UUID,
    body: KeywordRankScheduleCreate,
    ctx: RequestContext = Depends(
        require_feature(RANK_FEATURE, "geogrid.run", location_param="location_id")
    ),
    db: Session = Depends(get_db),
) -> KeywordRankScheduleOut:
    """Add a keyword/device/interval combination to be tracked on a schedule."""
    _assert_location_in_tenant(db, location_id, ctx)
    schedule = KeywordRankSchedule(
        location_id=location_id,
        keyword=body.keyword,
        device=body.device,
        interval_hours=body.interval_hours,
        is_active=True,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return KeywordRankScheduleOut.model_validate(schedule)


@router.get(
    "/locations/{location_id}/keyword-rank-schedules",
    response_model=list[KeywordRankScheduleOut],
)
def list_keyword_rank_schedules(
    location_id: UUID,
    ctx: RequestContext = Depends(
        require_feature(RANK_FEATURE, "geogrid.read", location_param="location_id")
    ),
    db: Session = Depends(get_db),
) -> list[KeywordRankScheduleOut]:
    """List all keyword schedules for a location."""
    _assert_location_in_tenant(db, location_id, ctx)
    rows = db.scalars(
        select(KeywordRankSchedule)
        .where(KeywordRankSchedule.location_id == location_id)
        .order_by(KeywordRankSchedule.keyword)
    ).all()
    return [KeywordRankScheduleOut.model_validate(r) for r in rows]


# --------------------------------------------------------------------------- #
# On-demand scan trigger                                                        #
# --------------------------------------------------------------------------- #

@router.post(
    "/locations/{location_id}/keyword-rank-scans",
    response_model=KeywordRankScanEnqueued,
    status_code=202,
)
def trigger_keyword_rank_scan(
    location_id: UUID,
    body: KeywordRankScanTrigger,
    ctx: RequestContext = Depends(
        require_feature(RANK_FEATURE, "geogrid.run", location_param="location_id")
    ),
    db: Session = Depends(get_db),
) -> KeywordRankScanEnqueued:
    """Enqueue an immediate keyword rank scan (outside the normal schedule)."""
    _assert_location_in_tenant(db, location_id, ctx)
    task = run_keyword_rank_scan.delay(
        tenant_id=str(ctx.tenant_id),
        location_id=str(location_id),
        keyword=body.keyword,
        device=body.device,
    )
    return KeywordRankScanEnqueued(
        status="queued",
        task_id=task.id,
        location_id=location_id,
        keyword=body.keyword,
        device=body.device,
    )


# --------------------------------------------------------------------------- #
# Results / trend history                                                       #
# --------------------------------------------------------------------------- #

@router.get(
    "/locations/{location_id}/keyword-rank-results",
    response_model=list[KeywordRankResultOut],
)
def list_keyword_rank_results(
    location_id: UUID,
    keyword: str | None = Query(None, description="Filter by keyword"),
    device: str | None = Query(None, description="Filter by device (desktop/mobile)"),
    limit: int = Query(100, ge=1, le=500),
    ctx: RequestContext = Depends(
        require_feature(RANK_FEATURE, "geogrid.read", location_param="location_id")
    ),
    db: Session = Depends(get_db),
) -> list[KeywordRankResultOut]:
    """Return rank results for a location, newest-first, for trend charting."""
    _assert_location_in_tenant(db, location_id, ctx)
    q = (
        select(KeywordRankResult)
        .where(KeywordRankResult.location_id == location_id)
        .order_by(KeywordRankResult.run_at.desc())
        .limit(limit)
    )
    if keyword:
        q = q.where(KeywordRankResult.keyword == keyword)
    if device:
        q = q.where(KeywordRankResult.device == device)

    rows = db.scalars(q).all()
    return [KeywordRankResultOut.model_validate(r) for r in rows]
