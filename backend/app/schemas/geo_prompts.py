"""Pydantic schemas for geo-prompts endpoint (API spec §6, P2C-4).

``GeoPromptOut`` is returned by GET; ``GeoPromptCreateIn`` is the request body for POST.
"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GeoPromptCreateIn(BaseModel):
    """Request body for POST /geo-prompts (account_manager+)."""

    niche: str | None = Field(None, max_length=120, description="Business niche (e.g. 'plumber'); NULL for global")
    prompt: str = Field(..., max_length=500, description="Prompt template")


class GeoPromptOut(BaseModel):
    """One prompt from the library (default or custom)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    niche: str | None = Field(None, description="NULL for global defaults")
    prompt: str
    is_custom: bool = Field(description="True if agency-added")


class GeoPromptsListOut(BaseModel):
    """Response for GET /geo-prompts."""

    prompts: list[GeoPromptOut]
