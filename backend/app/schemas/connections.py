"""Pydantic schemas for the GBP connection endpoints (API spec §5, PRD §6).

Request bodies never carry ``tenant_id`` — scoping comes from the token. Response
models deliberately omit the raw token entirely; ``token_ref`` is an internal vault
pointer and is not surfaced over the API.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    agency_gbp_project_id: str | None = None


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


# ── Agency-proxy connect (P1D-2) ──────────────────────────────────────────────

class ProxyConnectRequest(BaseModel):
    """Body of ``POST /connections/proxy``.

    ``agency_gbp_project_id`` is the agency's own Google-approved GBP project
    ID.  It is required because the project-ownership rule (PRD §6.3 ON-5 /
    PRD §9.1 rule 5) forbids an agency from routing programmatic access through
    the platform's own project.
    """

    client_id: UUID
    agency_gbp_project_id: str

    @field_validator("agency_gbp_project_id")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("agency_gbp_project_id must not be blank")
        return v


class ProxyConnectResponse(BaseModel):
    """Guided consent link the agency forwards to the client (P1D-2).

    Structurally identical to ``ConnectionStartResponse`` but named separately
    so the proxy flow's semantics remain explicit.
    """

    guided_link: str
    state: str


# ── CSV / batch location import (P1D-2) ───────────────────────────────────────

class CsvLocationRow(BaseModel):
    """One row in a CSV/batch location import."""

    google_place_id: str = Field(min_length=1)
    name: str = ""
    latitude: float | None = None
    longitude: float | None = None


class CsvImportRequest(BaseModel):
    """Body of ``POST /locations/import/csv``."""

    client_id: UUID
    rows: list[CsvLocationRow] = Field(min_length=1, max_length=500)


class CsvImportResponse(BaseModel):
    """Result of a CSV import."""

    client_id: UUID
    imported_count: int = Field(ge=0)
    locations: list[ImportedLocationOut]


# ── Connection health (P1D-3) ─────────────────────────────────────────────────

class ConnectionHealthOut(BaseModel):
    """Response for ``GET /connections/{id}/health`` (API spec §5).

    Surfaces token status, expiry metadata, and a ``reauth_url`` the caller
    can follow to re-connect the client — intentionally no token material.
    """

    connection_id: UUID
    token_status: str       # healthy | expiring | disconnected
    expires_at: datetime | None
    scopes: list[str]
    reauth_url: str
