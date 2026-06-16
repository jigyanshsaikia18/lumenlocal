"""Service seam for the AI-readiness audit (P2C-3).

Thin DB adapter around the pure :func:`~app.geo.ai_readiness.audit_ai_readiness`
engine: it loads the tenant-scoped location, hands its ``profile_data_live`` to
the engine, and returns the report. Kept separate from the router so the pure
scoring logic stays DB-free and tests can override this seam (as the
command-center endpoint does) rather than stand up Postgres.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.geo.ai_readiness import AiReadinessReport, audit_ai_readiness


class AiReadinessService:
    """Loads a location and audits its profile's GEO signals."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_report(
        self, tenant_id: UUID, location_id: UUID, now: datetime | None = None
    ) -> tuple[AiReadinessReport, datetime]:
        """Audit ``location_id`` (within ``tenant_id``); raise 404 if absent.

        Returns the report and the reference ``now`` it was generated against, so
        the endpoint can echo a ``generated_at`` consistent with the recency math.
        """
        from app.models.location import Location  # avoid circular import at module load

        loc = (
            self._db.query(Location)
            .filter(Location.tenant_id == tenant_id, Location.id == location_id)
            .first()
        )
        if loc is None:
            raise APIError(
                404,
                "not_found",
                "Location not found",
                {"location_id": str(location_id)},
            )
        now = now or datetime.now(tz=timezone.utc)
        return audit_ai_readiness(loc.profile_data_live or {}, now=now), now
