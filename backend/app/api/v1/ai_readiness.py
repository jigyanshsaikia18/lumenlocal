"""AI-readiness audit endpoint (API spec §6, PRD Module 3 GEO-7..GEO-9, P2C-3).

``GET /locations/{location_id}/ai-readiness``
  Scores the location's GEO signals (category specificity, products/services,
  NAP consistency, review/photo/Q&A/post freshness, attributes) and returns a
  prioritized, profile-specific GEO action list.

Read-only: derives everything from the stored profile, so the §12 chain stops at
step 3 — there is no quota meter (no scan is run) and no Google write (no Policy
Engine step). Gated by the ``ai_readiness`` feature flag and ``ai_readiness.read``
(analyst+).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.entitlements.gateway import require_feature
from app.geo.readiness_service import AiReadinessService
from app.schemas.ai_readiness import (
    AiReadinessOut,
    RecommendationOut,
    SignalScoreOut,
)
from app.security.context import RequestContext

router = APIRouter(tags=["ai_readiness"])

AI_READINESS_FEATURE = "ai_readiness"


def get_ai_readiness_service(db: Session = Depends(get_db)) -> AiReadinessService:
    """Request-scoped audit service (overridden in tests — no DB needed)."""
    return AiReadinessService(db)


@router.get(
    "/locations/{location_id}/ai-readiness",
    response_model=AiReadinessOut,
)
def get_ai_readiness(
    location_id: UUID,
    ctx: RequestContext = Depends(
        require_feature(
            AI_READINESS_FEATURE, "ai_readiness.read", location_param="location_id"
        )
    ),
    service: AiReadinessService = Depends(get_ai_readiness_service),
) -> AiReadinessOut:
    """Return the GEO audit + prioritized recommendations for a location.

    Entitlement-gated: ``ai_readiness`` off → ``403 feature_disabled``. The full
    RBAC + entitlement chain (§12 steps 1–3) runs before this handler.
    """
    report, generated_at = service.get_report(ctx.tenant_id, location_id)
    return AiReadinessOut(
        location_id=location_id,
        overall_score=report.overall_score,
        generated_at=generated_at,
        signals=[
            SignalScoreOut(
                key=s.key,
                label=s.label,
                weight=s.weight,
                score=s.score,
                detail=s.detail,
                action=s.action,
            )
            for s in report.signals
        ],
        recommendations=[
            RecommendationOut(
                signal=r.signal,
                action=r.action,
                priority=r.priority,
                impact_points=r.impact_points,
            )
            for r in report.recommendations
        ],
    )
