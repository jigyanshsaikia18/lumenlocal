"""Shared in-memory backend for entitlement gateway/admin tests (no Postgres).

``FakeEntitlementBackend`` satisfies both the read seam (``OverrideStore``) and the
write seam (``OverrideWriter``) over the same dicts, so a toggle written through the
admin path is visible to the next resolve — exactly what the DB does, without one.
"""
from __future__ import annotations

from uuid import UUID

from app.entitlements.registry import FeatureDef


class FakeEntitlementBackend:
    def __init__(
        self,
        features,
        *,
        plan_for_client=None,
        plan=None,
        client=None,
        location=None,
        location_client=None,
    ):
        self._features = list(features)
        self._plan_for_client = plan_for_client or {}
        self._plan = plan or {}
        self._client = {k: dict(v) for k, v in (client or {}).items()}
        self._location = {k: dict(v) for k, v in (location or {}).items()}
        self._location_client = location_client or {}

    # --- OverrideStore (read) ---------------------------------------------
    def feature_registry(self) -> list[FeatureDef]:
        return list(self._features)

    def plan_id_for_client(self, client_id: UUID) -> UUID | None:
        return self._plan_for_client.get(client_id)

    def client_id_for_location(self, location_id: UUID | None) -> UUID | None:
        return self._location_client.get(location_id) if location_id else None

    def plan_overrides(self, plan_id: UUID | None) -> dict[str, bool]:
        return dict(self._plan.get(plan_id, {})) if plan_id else {}

    def client_overrides(self, client_id: UUID) -> dict[str, bool]:
        return dict(self._client.get(client_id, {}))

    def location_overrides(self, location_id: UUID | None) -> dict[str, bool]:
        return dict(self._location.get(location_id, {})) if location_id else {}

    # --- OverrideWriter (write) -------------------------------------------
    def _scope_store(self, level: str) -> dict:
        return self._client if level == "client" else self._location

    def current_state(self, level: str, scope_id: UUID, feature_key: str) -> bool | None:
        return self._scope_store(level).get(scope_id, {}).get(feature_key)

    def upsert(
        self, level: str, scope_id: UUID, feature_key: str, state: bool, set_by
    ) -> None:
        self._scope_store(level).setdefault(scope_id, {})[feature_key] = state


def feat(key, deps=(), default=False) -> FeatureDef:
    return FeatureDef(key=key, name=key.title(), dependencies=deps, default_state=default)
