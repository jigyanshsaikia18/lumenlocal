"""Pydantic schemas for the toggle engine endpoints (API spec §4)."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class FeatureToggleRequest(BaseModel):
    """Body of ``PUT /clients|locations/{id}/features/{key}``."""

    state: bool


class FeatureToggleResponse(BaseModel):
    """Result of setting an override (echoes before/after for confirmation)."""

    feature_key: str
    level: str  # "client" | "location"
    scope_id: UUID
    previous_state: bool | None  # None = was inherited (no override at this level)
    state: bool


class ResolvedFeatureOut(BaseModel):
    """One feature's resolved on/off state and where the decision came from."""

    key: str
    enabled: bool
    source: str  # location | client | plan | default | dependency


class EntitlementResolveResponse(BaseModel):
    """The resolved feature set for a scope (``GET /entitlements/resolve``)."""

    client_id: UUID
    location_id: UUID | None = None
    features: list[ResolvedFeatureOut]


class FeatureOut(BaseModel):
    """A registered feature flag (``GET /features``)."""

    key: str
    name: str
    dependencies: list[str]
    default_state: bool


class ClientPreviewResponse(BaseModel):
    """The resolved entitlement set as seen by a given role (``GET /clients/{id}/preview``)."""

    client_id: UUID
    role: str
    features: list[ResolvedFeatureOut]
