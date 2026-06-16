"""Geo-prompts endpoint (API spec §6, P2C-4).

``GET /geo-prompts?niche=``
  List default + custom prompts visible to the tenant, optionally filtered by niche.
  Min role: ``analyst`` (``geo_prompts.read`` capability).

``POST /geo-prompts``
  Add a custom prompt scoped to the tenant.
  Min role: ``account_manager`` (``geo_prompts.write`` capability).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.entitlements.gateway import require_feature
from app.geo.prompts import GeoPromptService
from app.schemas.geo_prompts import GeoPromptCreateIn, GeoPromptOut, GeoPromptsListOut
from app.security.context import RequestContext

router = APIRouter(tags=["geo_prompts"])

GEO_PROMPTS_FEATURE = "geo_prompts"


def get_geo_prompt_service(db: Session = Depends(get_db)) -> GeoPromptService:
    """Request-scoped geo-prompts service."""
    return GeoPromptService(db)


@router.get("/geo-prompts", response_model=GeoPromptsListOut)
def list_geo_prompts(
    niche: str | None = None,
    ctx: RequestContext = Depends(
        require_feature(GEO_PROMPTS_FEATURE, "geo_prompts.read", client_param=None)
    ),
    service: GeoPromptService = Depends(get_geo_prompt_service),
) -> GeoPromptsListOut:
    """List default + custom prompts visible to the tenant.

    Optionally filter by niche. Returns both is_custom=false (defaults) and
    is_custom=true (tenant's custom prompts).
    """
    prompts = service.list_prompts(ctx.tenant_id, niche=niche)
    return GeoPromptsListOut(
        prompts=[
            GeoPromptOut(
                id=p.id,
                niche=p.niche,
                prompt=p.prompt,
                is_custom=p.is_custom,
            )
            for p in prompts
        ]
    )


@router.post("/geo-prompts", response_model=GeoPromptOut, status_code=201)
def create_geo_prompt(
    payload: GeoPromptCreateIn,
    ctx: RequestContext = Depends(
        require_feature(GEO_PROMPTS_FEATURE, "geo_prompts.write", client_param=None)
    ),
    service: GeoPromptService = Depends(get_geo_prompt_service),
) -> GeoPromptOut:
    """Add a custom prompt to the tenant's library.

    The prompt is scoped to the requesting tenant and marked is_custom=true.
    """
    prompt = service.add_custom_prompt(ctx.tenant_id, payload.niche, payload.prompt)
    return GeoPromptOut(
        id=prompt.id,
        niche=prompt.niche,
        prompt=prompt.prompt,
        is_custom=prompt.is_custom,
    )
