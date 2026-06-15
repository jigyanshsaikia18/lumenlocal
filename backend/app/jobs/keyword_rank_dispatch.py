"""``dispatch_keyword_rank_scans`` — periodic beat task (P2B-2).

Sweeps ``keyword_rank_schedules`` for rows that are due (i.e. never run, or
last run more than ``interval_hours`` hours ago) and enqueues one
``run_keyword_rank_scan`` job per due row.

This is a cross-tenant system sweep — it uses the privileged session (bypasses
RLS) like the token-health monitor, then scopes each enqueued job to its owning
tenant so the per-tenant fairness gate and RLS apply at execution time.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.jobs.keyword_rank_scan import run_keyword_rank_scan


def _due_schedules(session: Any) -> list[dict[str, Any]]:
    """Return all active schedules where the next run is overdue."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = session.execute(
        text(
            "SELECT s.id, s.keyword, s.device, s.interval_hours, s.last_run_at, "
            "       l.id AS location_id, l.tenant_id "
            "FROM keyword_rank_schedules s "
            "JOIN locations l ON l.id = s.location_id "
            "WHERE s.is_active = TRUE "
            "AND (s.last_run_at IS NULL "
            "     OR s.last_run_at + (s.interval_hours * INTERVAL '1 hour') <= :now)"
        ),
        {"now": now},
    ).fetchall()
    return [
        {
            "schedule_id": str(r.id),
            "location_id": str(r.location_id),
            "tenant_id": str(r.tenant_id),
            "keyword": r.keyword,
            "device": r.device,
        }
        for r in rows
    ]


@celery_app.task(name="keyword_rank.dispatch")
def dispatch_keyword_rank_scans() -> dict[str, Any]:
    """Enqueue rank scans for all due keyword schedules."""
    session = SessionLocal()
    try:
        due = _due_schedules(session)
    finally:
        session.close()

    for sched in due:
        run_keyword_rank_scan.delay(
            tenant_id=sched["tenant_id"],
            location_id=sched["location_id"],
            keyword=sched["keyword"],
            device=sched["device"],
        )

    return {"dispatched": len(due)}
