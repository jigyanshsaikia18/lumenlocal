"""The entitlement *write* path: set an override, audit it, refresh the cache.

The read side (``EntitlementService``) resolves the 4-level set; this is its mirror
for changes. Setting a client- or location-level override (API spec §4
``PUT /clients/{id}/features/{key}`` and ``/locations/...``) must, atomically from
the caller's point of view:

1. **Guard dependencies** (FT-4) — enabling a feature whose prerequisite is off is
   rejected (``409``) instead of silently forced off, via ``validate_can_enable``.
2. **Persist** the override (``OverrideWriter`` — update-or-insert).
3. **Audit** the change to the immutable ``audit_log`` (RBAC-5, FT-6) with
   before/after state.
4. **Invalidate** the client's cached resolution so the toggle takes effect at once
   on this node, ahead of the TTL (PRD §5 FT-2).

The writer and audit sink are injected seams (like the rest of ``app.entitlements``
and ``app.compliance``), so the whole flow is unit-testable without Postgres.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.audit.log import AuditLogEntry, AuditLogSink
from app.core.errors import APIError
from app.entitlements.cache import TtlEntitlementCache, entitlement_cache
from app.entitlements.registry import index_by_key
from app.entitlements.repository import EntitlementService
from app.entitlements.resolver import DependencyError, validate_can_enable
from app.security.context import RequestContext

# Override levels (also the audit ``target_type``). The platform/plan level is set
# elsewhere (billing); per-client and per-location overrides are the admin console's job.
LEVEL_CLIENT = "client"
LEVEL_LOCATION = "location"

ACTION_SET_OVERRIDE = "entitlement.override.set"

# Level → override table. Fixed internal mapping (never interpolate user input).
_TABLE = {LEVEL_CLIENT: "client_features", LEVEL_LOCATION: "location_features"}


@dataclass(frozen=True)
class ToggleResult:
    """Outcome of a set-override call (for the API response + the audit before/after)."""

    feature_key: str
    level: str
    scope_id: UUID
    previous_state: bool | None  # None = was inherited (no override at this level)
    state: bool


class OverrideWriter(Protocol):
    """Reads/writes a single override row at one level (mock this in tests)."""

    def current_state(self, level: str, scope_id: UUID, feature_key: str) -> bool | None: ...

    def upsert(
        self, level: str, scope_id: UUID, feature_key: str, state: bool, set_by: UUID | None
    ) -> None: ...


class SqlAlchemyOverrideWriter:
    """Update-or-insert an override row in ``client_features`` / ``location_features``.

    There is no unique ``(scope_id, feature_key)`` constraint on these tables, so we
    update the existing row in place and insert only when none exists — keeping a
    single authoritative state per (scope, feature) that the resolver reads back.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def current_state(self, level: str, scope_id: UUID, feature_key: str) -> bool | None:
        table = _TABLE[level]
        row = self._session.execute(
            text(
                f"SELECT state FROM {table} "
                "WHERE scope_id = :sid AND feature_key = :k ORDER BY set_at DESC LIMIT 1"
            ),
            {"sid": scope_id, "k": feature_key},
        ).first()
        return None if row is None else row.state

    def upsert(
        self, level: str, scope_id: UUID, feature_key: str, state: bool, set_by: UUID | None
    ) -> None:
        table = _TABLE[level]
        params = {"sid": scope_id, "k": feature_key, "state": state, "set_by": set_by}
        result = self._session.execute(
            text(
                f"UPDATE {table} SET state = :state, set_by = :set_by, "
                "set_at = CURRENT_TIMESTAMP WHERE scope_id = :sid AND feature_key = :k"
            ),
            params,
        )
        if result.rowcount == 0:
            self._session.execute(
                text(
                    f"INSERT INTO {table} (scope_id, feature_key, state, set_by) "
                    "VALUES (:sid, :k, :state, :set_by)"
                ),
                params,
            )


class EntitlementAdminService:
    """Set a feature override with dependency-guarding, auditing, and cache refresh."""

    def __init__(
        self,
        writer: OverrideWriter,
        service: EntitlementService,
        audit_sink: AuditLogSink,
        *,
        cache: TtlEntitlementCache = entitlement_cache,
    ) -> None:
        self._writer = writer
        self._service = service
        self._audit = audit_sink
        self._cache = cache

    def set_client_override(
        self, ctx: RequestContext, client_id: UUID, feature_key: str, state: bool
    ) -> ToggleResult:
        """Set ``feature_key`` to ``state`` for a whole client."""
        return self._set(
            ctx,
            level=LEVEL_CLIENT,
            scope_id=client_id,
            client_id=client_id,
            location_id=None,
            feature_key=feature_key,
            state=state,
        )

    def set_location_override(
        self,
        ctx: RequestContext,
        location_id: UUID,
        feature_key: str,
        state: bool,
        *,
        client_id: UUID,
    ) -> ToggleResult:
        """Set ``feature_key`` to ``state`` for one location (``client_id`` is its owner)."""
        return self._set(
            ctx,
            level=LEVEL_LOCATION,
            scope_id=location_id,
            client_id=client_id,
            location_id=location_id,
            feature_key=feature_key,
            state=state,
        )

    def _set(
        self,
        ctx: RequestContext,
        *,
        level: str,
        scope_id: UUID,
        client_id: UUID,
        location_id: UUID | None,
        feature_key: str,
        state: bool,
    ) -> ToggleResult:
        features = self._service.registry()
        if feature_key not in index_by_key(features):
            raise APIError(404, "feature_not_found", f"Unknown feature '{feature_key}'")

        # FT-4: a feature can only be enabled if its dependencies resolve on.
        if state:
            resolved = self._service.resolve(client_id, location_id)
            try:
                validate_can_enable(feature_key, resolved, features)
            except DependencyError as exc:
                raise APIError(
                    409, "dependency_not_enabled", str(exc), {"feature": feature_key}
                ) from exc

        previous = self._writer.current_state(level, scope_id, feature_key)
        self._writer.upsert(level, scope_id, feature_key, state, ctx.user_id)

        self._audit.record(
            AuditLogEntry(
                tenant_id=ctx.tenant_id,
                actor_user_id=ctx.user_id,
                action=ACTION_SET_OVERRIDE,
                target_type=level,
                target_id=scope_id,
                before={"feature_key": feature_key, "state": previous},
                after={"feature_key": feature_key, "state": state},
            )
        )

        # Immediate effect on this node; the TTL bounds staleness on the others.
        self._cache.invalidate_client(client_id)
        return ToggleResult(
            feature_key=feature_key,
            level=level,
            scope_id=scope_id,
            previous_state=previous,
            state=state,
        )
