"""Entitlement gateway — step 3 of the §12 chain (``403 feature_disabled``).

After authentication (step 1) and RBAC (step 2), the gateway resolves the caller's
4-level feature set for the request's scope and **blocks a disabled feature with
``403 feature_disabled``** (API spec §1, §12; PRD §5.3). This is the wiring that
turns the pure resolver (P1C-1) into an enforced gate on real traffic.

A route declares the gate as one dependency::

    @router.post("/locations/{location_id}/geogrid-scans")
    def create_scan(location_id: UUID, body: ...,
        ctx: RequestContext = Depends(
            require_feature("geogrid", "geogrid.run",
                            client_param=None, location_param="location_id"))):
        ...

``require_feature`` composes the RBAC check (``require`` over the listed
capabilities) with the entitlement check, preserving the chain order. Resolution
goes through :data:`~app.entitlements.cache.entitlement_cache`, so a hot path does
not hit the DB every request, while a toggle still takes effect within the cache TTL
(PRD §5 FT-2). The scope is read from path params: ``client_param`` and/or
``location_param`` (at least one must be present and resolve to the owning client).
"""
from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.session import get_db
from app.entitlements.cache import entitlement_cache
from app.entitlements.repository import EntitlementService, SqlAlchemyOverrideStore
from app.security.context import RequestContext
from app.security.deps import get_request_context, require


def get_entitlement_service(db: Session = Depends(get_db)) -> EntitlementService:
    """Provide a request-scoped service over the live override tables.

    Overridden in tests with a service backed by an in-memory ``OverrideStore`` so
    the gateway is exercised without Postgres.
    """
    return EntitlementService(SqlAlchemyOverrideStore(db))


def feature_disabled(feature_key: str) -> APIError:
    """The canonical ``403 feature_disabled`` for a toggled-off capability."""
    return APIError(
        403,
        "feature_disabled",
        f"The '{feature_key}' feature is not enabled for this account",
        {"feature": feature_key},
    )


def _uuid_param(request: Request, name: str | None) -> UUID | None:
    if name is None:
        return None
    raw = request.path_params.get(name)
    if raw is None:
        return None
    return raw if isinstance(raw, UUID) else UUID(str(raw))


def require_feature(
    feature_key: str,
    *capabilities: str,
    client_param: str | None = "client_id",
    location_param: str | None = None,
) -> Callable[..., RequestContext]:
    """Build a dependency that runs RBAC then blocks ``feature_key`` when disabled.

    ``capabilities`` are the RBAC requirements (step 2); all must be held. The scope
    for entitlement resolution (step 3) is taken from the path: the owning client
    from ``client_param`` and, when given, the specific location from
    ``location_param``. A disabled feature raises ``403 feature_disabled``; the
    passing ``RequestContext`` is returned for the handler to reuse.

    Pass ``client_param=None, location_param=None`` for account-wide routes that
    have no client/location in their path (e.g. ``/geo-prompts``) — entitlements
    then resolve against the global plan/registry only (no client-level override).
    """
    # Run the capability check first so the chain order (RBAC → entitlement) holds.
    # ``require`` scopes its grant check to the client when we have one in the path.
    rbac = (
        require(*capabilities, scope_param=client_param)
        if capabilities
        else get_request_context
    )

    def dependency(
        request: Request,
        ctx: RequestContext = Depends(rbac),
        service: EntitlementService = Depends(get_entitlement_service),
    ) -> RequestContext:
        client_id = _uuid_param(request, client_param)
        location_id = _uuid_param(request, location_param)
        if client_id is None:
            client_id = service.client_id_for_location(location_id)
        if client_id is None and (client_param is not None or location_param is not None):
            # Misconfigured route: a scope param was declared but didn't resolve.
            raise APIError(
                500, "scope_unresolved", "Could not resolve client scope for entitlement check"
            )
        resolved = entitlement_cache.resolve(
            client_id, location_id, service.resolve
        )
        rf = resolved.get(feature_key)
        if rf is None or not rf.enabled:
            raise feature_disabled(feature_key)
        return ctx

    return dependency
