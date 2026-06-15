"""GBP token health monitor — background worker (P1D-3, PRD §6 ON-6).

Scans all ``gbp_connections`` for tokens that are expiring soon or already
disconnected, flags their status, and fires operator alerts with a re-auth link
so the agency can act before a client's GBP access goes dark.

The core check logic (``scan_connections``) is a plain function that accepts any
SQLAlchemy-session-like object and an ``AlertSink``, so tests can drive it without
Celery, Redis, or Postgres. The Celery task wraps it with a privileged session
(bypasses RLS) because this is a cross-tenant system sweep, not a per-tenant user
action — the privileged engine is the right tool here (see app/db/session.py).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.alerts import (
    SEVERITY_CRITICAL,
    SEVERITY_WARNING,
    Alert,
    AlertSink,
    alert_sink as _default_sink,
)
from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.connection import GbpConnection


def scan_connections(session: Any, sink: AlertSink) -> dict[str, int]:
    """Flag expiring connections and alert on expiring/disconnected tokens.

    State-change semantics:
    - ``healthy`` + ``expires_at <= now + warning_days`` → set ``expiring``, alert once.
    - ``disconnected`` → alert on every sweep (sink owns deduplication in production).
    - All other statuses (``expiring`` already flagged, no expiry set) are ignored.

    Returns ``{"expiring_flagged": N, "disconnected_alerted": M}`` for observability.
    Commits the session on success.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC matches DB column
    threshold = now + timedelta(days=settings.token_expiry_warning_days)

    expiring_count = 0
    disconnected_count = 0

    for conn in session.query(GbpConnection).all():
        reauth_url = f"{settings.frontend_url}/connections/{conn.id}/reauth"

        if (
            conn.token_status == "healthy"
            and conn.expires_at is not None
            and conn.expires_at <= threshold
        ):
            conn.token_status = "expiring"
            expiring_count += 1
            sink.fire(
                Alert(
                    kind="token_expiring",
                    severity=SEVERITY_WARNING,
                    summary=f"GBP token {conn.id} expires at {conn.expires_at}",
                    context={
                        "connection_id": str(conn.id),
                        "client_id": str(conn.client_id),
                        "expires_at": str(conn.expires_at),
                        "reauth_url": reauth_url,
                    },
                )
            )

        elif conn.token_status == "disconnected":
            disconnected_count += 1
            sink.fire(
                Alert(
                    kind="token_disconnected",
                    severity=SEVERITY_CRITICAL,
                    summary=f"GBP connection {conn.id} is disconnected; re-auth required",
                    context={
                        "connection_id": str(conn.id),
                        "client_id": str(conn.client_id),
                        "reauth_url": reauth_url,
                    },
                )
            )

    session.commit()
    return {"expiring_flagged": expiring_count, "disconnected_alerted": disconnected_count}


@celery_app.task(name="token_health.check")
def check_token_health() -> dict[str, Any]:
    """Periodic beat task: scan all GBP connections for token health issues."""
    session = SessionLocal()
    try:
        return scan_connections(session, _default_sink)
    finally:
        session.close()
