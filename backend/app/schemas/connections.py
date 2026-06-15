"""Pydantic schemas for the GBP connection endpoints (API spec §5, PRD §6).

Request bodies never carry ``tenant_id`` — scoping comes from the token. Response
models deliberately omit the raw token entirely; ``token_ref`` is an internal vault
pointer and is not surfaced over the API.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConnectionStartRequest(BaseModel):
    """Body of ``POST /connections/oauth/start``."""

    client_id: UUID
    connect_method: str = "self_serve"  # self_serve | agency_proxy (PRD §6)


class ConnectionStartResponse(BaseModel):
    """Consent URL to redirect the client to, plus the signed CSRF ``state``."""

    consent_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    """Body of ``POST /connections/oauth/callback`` (the redirect's code + state)."""

    code: str
    state: str


class ConnectionOut(BaseModel):
    """A persisted connection — note the absence of any token material."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    connect_method: str
    token_status: str
    scopes: list[str]
    expires_at: datetime | None


class ImportLocationsRequest(BaseModel):
    """Body of ``POST /locations/import``."""

    connection_id: UUID


class ImportedLocationOut(BaseModel):
    """One location created by an import."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    google_place_id: str | None
    latitude: float | None
    longitude: float | None


class ImportLocationsResponse(BaseModel):
    """Result of ``POST /locations/import``: what was newly imported."""

    connection_id: UUID
    imported_count: int = Field(ge=0)
    locations: list[ImportedLocationOut]
