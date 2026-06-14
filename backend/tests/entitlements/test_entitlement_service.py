"""P1C-1: EntitlementService end-to-end with the DB mocked.

The DB is mocked at the ``OverrideStore`` seam by an in-memory ``FakeOverrideStore``
— no Postgres. These tests prove the service wires the four layers (resolved via
``plan_id_for_client`` → plan → client → location) into the pure resolver and
that all four precedence levels and the dependency rule hold through that path.
"""
from uuid import UUID, uuid4

from app.entitlements.registry import FeatureDef
from app.entitlements.repository import EntitlementService, OverrideStore
from app.entitlements.resolver import (
    SOURCE_CLIENT,
    SOURCE_DEFAULT,
    SOURCE_DEPENDENCY,
    SOURCE_LOCATION,
    SOURCE_PLAN,
)


def feat(key, deps=(), default=False):
    return FeatureDef(key=key, name=key.title(), dependencies=deps, default_state=default)


FEATURES = [
    feat("geogrid", default=False),
    feat("protection", default=True),
    feat("review_inbox", default=False),
    feat("ai_writer", deps=("review_inbox",), default=False),
]


class FakeOverrideStore:
    """In-memory stand-in for the DB (satisfies the OverrideStore Protocol)."""

    def __init__(self, *, plan_for_client=None, plan=None, client=None, location=None):
        self._plan_for_client = plan_for_client or {}
        self._plan = plan or {}
        self._client = client or {}
        self._location = location or {}

    def feature_registry(self) -> list[FeatureDef]:
        return list(FEATURES)

    def plan_id_for_client(self, client_id: UUID) -> UUID | None:
        return self._plan_for_client.get(client_id)

    def plan_overrides(self, plan_id: UUID | None) -> dict[str, bool]:
        return dict(self._plan.get(plan_id, {})) if plan_id else {}

    def client_overrides(self, client_id: UUID) -> dict[str, bool]:
        return dict(self._client.get(client_id, {}))

    def location_overrides(self, location_id: UUID | None) -> dict[str, bool]:
        return dict(self._location.get(location_id, {})) if location_id else {}


def test_fake_satisfies_protocol():
    store: OverrideStore = FakeOverrideStore()
    assert store.feature_registry()  # the Protocol is structurally satisfied


def test_service_returns_defaults_when_store_is_empty():
    svc = EntitlementService(FakeOverrideStore())
    resolved = svc.resolve(uuid4())
    assert resolved["geogrid"].source == SOURCE_DEFAULT
    assert resolved["protection"].enabled is True


def test_service_applies_plan_override():
    client_id, plan_id = uuid4(), uuid4()
    svc = EntitlementService(
        FakeOverrideStore(
            plan_for_client={client_id: plan_id},
            plan={plan_id: {"geogrid": True}},
        )
    )
    resolved = svc.resolve(client_id)
    assert (resolved["geogrid"].enabled, resolved["geogrid"].source) == (True, SOURCE_PLAN)


def test_service_client_override_beats_plan():
    client_id, plan_id = uuid4(), uuid4()
    svc = EntitlementService(
        FakeOverrideStore(
            plan_for_client={client_id: plan_id},
            plan={plan_id: {"geogrid": True}},
            client={client_id: {"geogrid": False}},
        )
    )
    resolved = svc.resolve(client_id)
    assert (resolved["geogrid"].enabled, resolved["geogrid"].source) == (False, SOURCE_CLIENT)


def test_service_location_override_beats_client():
    client_id, plan_id, location_id = uuid4(), uuid4(), uuid4()
    svc = EntitlementService(
        FakeOverrideStore(
            plan_for_client={client_id: plan_id},
            plan={plan_id: {"geogrid": False}},
            client={client_id: {"geogrid": False}},
            location={location_id: {"geogrid": True}},
        )
    )
    resolved = svc.resolve(client_id, location_id)
    assert (resolved["geogrid"].enabled, resolved["geogrid"].source) == (True, SOURCE_LOCATION)


def test_service_ignores_location_layer_when_no_location_given():
    client_id, location_id = uuid4(), uuid4()
    svc = EntitlementService(
        FakeOverrideStore(location={location_id: {"geogrid": True}})
    )
    # No location_id passed → the location override must not leak in.
    resolved = svc.resolve(client_id)
    assert resolved["geogrid"].enabled is False
    assert resolved["geogrid"].source == SOURCE_DEFAULT


def test_service_enforces_dependency_rule():
    """ai_writer enabled at location but review_inbox off → forced off, end-to-end."""
    client_id, location_id = uuid4(), uuid4()
    svc = EntitlementService(
        FakeOverrideStore(location={location_id: {"ai_writer": True}})
    )
    resolved = svc.resolve(client_id, location_id)
    assert resolved["ai_writer"].enabled is False
    assert resolved["ai_writer"].source == SOURCE_DEPENDENCY


def test_is_enabled_convenience():
    client_id, plan_id = uuid4(), uuid4()
    svc = EntitlementService(
        FakeOverrideStore(
            plan_for_client={client_id: plan_id},
            plan={plan_id: {"geogrid": True}},
        )
    )
    assert svc.is_enabled("geogrid", client_id) is True
    assert svc.is_enabled("ai_writer", client_id) is False
    assert svc.is_enabled("nonexistent_feature", client_id) is False
