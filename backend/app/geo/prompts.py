"""Geo-prompts service: retrieve and manage the prompt library.

Separates default (global, niche-aware) prompts from custom (tenant-owned) ones.
Merges both sets for API responses.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.geo_prompt import GeoPrompt


class GeoPromptService:
    """Manage default + custom prompt library."""

    def __init__(self, db: Session):
        self.db = db

    def list_prompts(self, tenant_id: UUID, niche: str | None = None) -> list[GeoPrompt]:
        """Fetch all prompts visible to the tenant: defaults + custom.

        If niche is provided, filter by niche. Returns both is_custom=false
        (default) and is_custom=true (custom to this tenant) prompts.
        """
        query = self.db.query(GeoPrompt).filter(
            or_(
                GeoPrompt.is_custom == False,  # noqa: E712
                GeoPrompt.tenant_id == tenant_id,
            )
        )

        if niche:
            query = query.filter(GeoPrompt.niche == niche)

        return query.all()

    def add_custom_prompt(self, tenant_id: UUID, niche: str | None, prompt: str) -> GeoPrompt:
        """Add a custom prompt for the tenant."""
        custom_prompt = GeoPrompt(
            niche=niche,
            prompt=prompt,
            is_custom=True,
            tenant_id=tenant_id,
        )
        self.db.add(custom_prompt)
        self.db.commit()
        self.db.refresh(custom_prompt)
        return custom_prompt
