"""The DB seam for entitlement resolution.

``OverrideStore`` is the narrow interface the resolver needs from the database:
the feature registry and the per-scope override maps. Splitting it out keeps the
resolver pure and lets unit tests inject an in-memory fake instead of Postgres.

``SqlAlchemyOverrideStore`` is the production implementation (thin ``text()``
queries against the §3 tables). ``EntitlementService`` composes a store with the
pure resolver and is what handlers/CLI use.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.entitlements.registry import FeatureDef
from app.entitlements.resolver import ResolvedFeature, resolve_entitlements


class OverrideStore(Protocol):
    """What the resolver needs from persistence (mock this in tests)."""

    def feature_registry(self) -> list[FeatureDef]: ...

    def plan_id_for_client(self, client_id: UUID | None) -> UUID | None: ...

    def client_id_for_location(self, location_id: UUID | None) -> UUID | None: ...

    def plan_overrides(self, plan_id: UUID | None) -> dict[str, bool]: ...

    def client_overrides(self, client_id: UUID | None) -> dict[str, bool]: ...

    def location_overrides(self, location_id: UUID | None) -> dict[str, bool]: ...


class SqlAlchemyOverrideStore:
    """Production ``OverrideStore`` over the entitlement tables (schema §3).

    Runs as the ``lumen_app`` role at runtime; the migration grants it SELECT on
    these tables. Integration-tested against Postgres (no DB on this box), so the
    unit suite mocks the store rather than this class.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def feature_registry(self) -> list[FeatureDef]:
        rows = self._session.execute(
            text("SELECT key, name, dependencies, default_state FROM features")
        )
        return [
            FeatureDef(
                key=r.key,
                name=r.name,
                dependencies=tuple(r.dependencies or ()),
                default_state=r.default_state,
            )
            for r in rows
        ]

    def plan_id_for_client(self, client_id: UUID | None) -> UUID | None:
        if client_id is None:
            return None
        return self._session.execute(
            text(
                "SELECT t.plan_id FROM clients c "
                "JOIN tenants t ON t.id = c.tenant_id WHERE c.id = :cid"
            ),
            {"cid": client_id},
        ).scalar_one_or_none()

    def client_id_for_location(self, location_id: UUID | None) -> UUID | None:
        """Owning client of a location — used to resolve scope on location-only routes."""
        if location_id is None:
            return None
        return self._session.execute(
            text("SELECT client_id FROM locations WHERE id = :lid"),
            {"lid": location_id},
        ).scalar_one_or_none()

    def _overrides(self, table: str, scope_id: UUID | None) -> dict[str, bool]:
        if scope_id is None:
            return {}
        rows = self._session.execute(
            text(f"SELECT feature_key, state FROM {table} WHERE scope_id = :sid"),
            {"sid": scope_id},
        )
        return {r.feature_key: r.state for r in rows}

    def plan_overrides(self, plan_id: UUID | None) -> dict[str, bool]:
        return self._overrides("plan_features", plan_id)

    def client_overrides(self, client_id: UUID | None) -> dict[str, bool]:
        return self._overrides("client_features", client_id)

    def location_overrides(self, location_id: UUID | None) -> dict[str, bool]:
        return self._overrides("location_features", location_id)


class EntitlementService:
    """Resolve the effective feature set for a client (optionally a location)."""

    def __init__(self, store: OverrideStore) -> None:
        self._store = store

    def registry(self) -> list[FeatureDef]:
        """The feature registry (for write-path dependency validation + GET /features)."""
        return self._store.feature_registry()

    def resolve(
        self, client_id: UUID | None, location_id: UUID | None = None
    ) -> dict[str, ResolvedFeature]:
        """Load the four layers for this scope and resolve them (precedence + deps)."""
        plan_id = self._store.plan_id_for_client(client_id)
        return resolve_entitlements(
            self._store.feature_registry(),
            plan_overrides=self._store.plan_overrides(plan_id),
            client_overrides=self._store.client_overrides(client_id),
            location_overrides=self._store.location_overrides(location_id),
        )

    # Convenience for callers that only need the boolean view.
    def is_enabled(
        self, feature_key: str, client_id: UUID | None, location_id: UUID | None = None
    ) -> bool:
        resolved = self.resolve(client_id, location_id)
        rf = resolved.get(feature_key)
        return bool(rf and rf.enabled)

    def client_id_for_location(self, location_id: UUID | None) -> UUID | None:
        """Resolve a location's owning client (delegates to the store)."""
        return self._store.client_id_for_location(location_id)


# Help static checkers confirm the concrete store satisfies the Protocol.
_STORE_CHECK: type[OverrideStore] = SqlAlchemyOverrideStore
