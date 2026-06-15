"""Toggle-engine endpoints (API spec §4): read the resolved set, flip overrides.

These are the admin console's API for the client-wise feature-toggle engine (PRD §5).
``PUT`` writes an override, audits it, and invalidates the cache so the change takes
effect within ~1 minute without a deploy (FT-2/FT-6). ``GET`` surfaces the resolved
4-level set and the feature registry.

The request chain (§12) is honoured: ``require(...)`` enforces RBAC (step 2); the
override writes are admin-only (``entitlements.override``), reads are ``analyst+``
(``entitlements.resolve`` / ``features.read``). Provider seams
(``get_entitlement_admin`` / ``get_entitlement_service``) are overridden in tests so
the endpoints run without Postgres.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.audit.log import SqlAlchemyAuditLogSink
from app.core.errors import APIError
from app.db.session import get_db
from app.entitlements.admin import EntitlementAdminService, SqlAlchemyOverrideWriter
from app.entitlements.cache import entitlement_cache
from app.entitlements.gateway import get_entitlement_service
from app.entitlements.repository import EntitlementService, SqlAlchemyOverrideStore
from app.schemas.entitlements import (
    EntitlementResolveResponse,
    FeatureOut,
    FeatureToggleRequest,
    FeatureToggleResponse,
    ResolvedFeatureOut,
)
from app.security.context import RequestContext
from app.security.deps import require

router = APIRouter(tags=["entitlements"])


def get_entitlement_admin(db: Session = Depends(get_db)) -> EntitlementAdminService:
    """Compose the write-path service over the live tables (overridden in tests)."""
    service = EntitlementService(SqlAlchemyOverrideStore(db))
    return EntitlementAdminService(
        SqlAlchemyOverrideWriter(db), service, SqlAlchemyAuditLogSink(db)
    )


@router.put("/clients/{client_id}/features/{feature_key}", response_model=FeatureToggleResponse)
def set_client_feature(
    client_id: UUID,
    feature_key: str,
    body: FeatureToggleRequest,
    ctx: RequestContext = Depends(require("entitlements.override", scope_param="client_id")),
    admin: EntitlementAdminService = Depends(get_entitlement_admin),
    db: Session = Depends(get_db),
) -> FeatureToggleResponse:
    """Set a client-level feature override (toggle on/off for a whole client)."""
    result = admin.set_client_override(ctx, client_id, feature_key, body.state)
    db.commit()
    return FeatureToggleResponse(**result.__dict__)


@router.put("/locations/{location_id}/features/{feature_key}", response_model=FeatureToggleResponse)
def set_location_feature(
    location_id: UUID,
    feature_key: str,
    body: FeatureToggleRequest,
    ctx: RequestContext = Depends(require("entitlements.override")),
    admin: EntitlementAdminService = Depends(get_entitlement_admin),
    service: EntitlementService = Depends(get_entitlement_service),
    db: Session = Depends(get_db),
) -> FeatureToggleResponse:
    """Set a location-level feature override (most specific scope)."""
    client_id = service.client_id_for_location(location_id)
    if client_id is None:
        raise APIError(404, "location_not_found", "Location not found")
    result = admin.set_location_override(
        ctx, location_id, feature_key, body.state, client_id=client_id
    )
    db.commit()
    return FeatureToggleResponse(**result.__dict__)


@router.get("/entitlements/resolve", response_model=EntitlementResolveResponse)
def resolve_entitlements_endpoint(
    client_id: UUID = Query(...),
    location_id: UUID | None = Query(None),
    ctx: RequestContext = Depends(require("entitlements.resolve")),
    service: EntitlementService = Depends(get_entitlement_service),
) -> EntitlementResolveResponse:
    """Return the resolved on/off set for a client (optionally a location)."""
    resolved = entitlement_cache.resolve(client_id, location_id, service.resolve)
    return EntitlementResolveResponse(
        client_id=client_id,
        location_id=location_id,
        features=[
            ResolvedFeatureOut(key=rf.key, enabled=rf.enabled, source=rf.source)
            for rf in resolved.values()
        ],
    )


@router.get("/features", response_model=list[FeatureOut])
def list_features(
    ctx: RequestContext = Depends(require("features.read")),
    service: EntitlementService = Depends(get_entitlement_service),
) -> list[FeatureOut]:
    """List the registered feature flags and their dependencies (FT-1)."""
    return [
        FeatureOut(
            key=f.key,
            name=f.name,
            dependencies=list(f.dependencies),
            default_state=f.default_state,
        )
        for f in service.registry()
    ]
