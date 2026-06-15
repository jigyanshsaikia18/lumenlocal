"""P1E-2: multi-location command center — roll-up aggregation + entitlement gate.

Two acceptance criteria verified here:
1. ``compute_rollup`` produces totals that equal the arithmetic sum across all
   returned locations (PRD §7 D-3: "roll-up KPIs across a client's locations").
2. When ``dashboard_multi_location`` is toggled off for the client the endpoint
   returns ``403 feature_disabled`` (PRD §7 D-6: entitlements hidden when off).

No Postgres: the location service dependency is overridden with a fake that
returns fixed data, and the entitlement service uses ``FakeEntitlementBackend``.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.locations import MULTI_LOCATION_FEATURE, get_location_service, router
from app.core.errors import install_error_handlers
from app.entitlements.gateway import get_entitlement_service
from app.entitlements.repository import EntitlementService
from app.locations.service import (
    CommandCenterData,
    LocationKPIs,
    LocationSummary,
    compute_rollup,
)
from app.entitlements.cache import entitlement_cache
from app.security.context import RequestContext, RoleAssignment
from app.security.deps import get_request_context
from tests.entitlements.fakes import FakeEntitlementBackend, feat

CLIENT_ID = UUID("c0000000-0000-0000-0000-000000000001")


@pytest.fixture(autouse=True)
def _clear_entitlement_cache():
    """The module-level cache is shared across tests; clear it before each run."""
    entitlement_cache.clear()
    yield
    entitlement_cache.clear()

_FEATURES = [feat(MULTI_LOCATION_FEATURE, default=True)]


def _principal() -> RequestContext:
    return RequestContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        roles=(RoleAssignment(role="analyst"),),
    )


class FakeLocationService:
    def __init__(self, data: CommandCenterData) -> None:
        self._data = data

    def get_command_center(self, tenant_id: UUID, client_id: UUID) -> CommandCenterData:
        return self._data


def _build_app(data: CommandCenterData, *, feature_enabled: bool) -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(router)

    client_overrides = {} if feature_enabled else {CLIENT_ID: {MULTI_LOCATION_FEATURE: False}}
    backend = FakeEntitlementBackend(_FEATURES, client=client_overrides)

    app.dependency_overrides[get_request_context] = _principal
    app.dependency_overrides[get_entitlement_service] = lambda: EntitlementService(backend)
    app.dependency_overrides[get_location_service] = lambda: FakeLocationService(data)
    return app


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_LOCATIONS = [
    LocationSummary(
        id=uuid4(),
        name="Downtown Branch",
        latitude=37.7749,
        longitude=-122.4194,
        health_score=88,
        kpis=LocationKPIs(views=5000, calls=120, directions=300, website_clicks=400),
    ),
    LocationSummary(
        id=uuid4(),
        name="Uptown Branch",
        latitude=37.7849,
        longitude=-122.4094,
        health_score=64,
        kpis=LocationKPIs(views=3200, calls=80, directions=150, website_clicks=200),
    ),
    LocationSummary(
        id=uuid4(),
        name="Westside Branch",
        latitude=37.7649,
        longitude=-122.4294,
        health_score=38,
        kpis=LocationKPIs(views=1800, calls=45, directions=90, website_clicks=120),
    ),
]

# Precomputed so the test asserts on concrete values, not re-derived ones.
_EXPECTED_VIEWS = 5000 + 3200 + 1800   # 10000
_EXPECTED_CALLS = 120 + 80 + 45        # 245
_EXPECTED_DIRS = 300 + 150 + 90        # 540
_EXPECTED_CLICKS = 400 + 200 + 120     # 720

_DATA = CommandCenterData(
    client_id=CLIENT_ID,
    total_locations=len(_LOCATIONS),
    rollup=LocationKPIs(
        views=_EXPECTED_VIEWS,
        calls=_EXPECTED_CALLS,
        directions=_EXPECTED_DIRS,
        website_clicks=_EXPECTED_CLICKS,
    ),
    locations=_LOCATIONS,
)


# ---------------------------------------------------------------------------
# Unit: pure roll-up function
# ---------------------------------------------------------------------------

def test_compute_rollup_sums_all_kpis():
    """Rollup equals the element-wise sum across location KPIs (the core invariant)."""
    rollup = compute_rollup(_LOCATIONS)
    assert rollup.views == _EXPECTED_VIEWS
    assert rollup.calls == _EXPECTED_CALLS
    assert rollup.directions == _EXPECTED_DIRS
    assert rollup.website_clicks == _EXPECTED_CLICKS


def test_compute_rollup_empty_list_returns_zeros():
    rollup = compute_rollup([])
    assert rollup.views == 0
    assert rollup.calls == 0
    assert rollup.directions == 0
    assert rollup.website_clicks == 0


# ---------------------------------------------------------------------------
# Integration: HTTP endpoint
# ---------------------------------------------------------------------------

def test_command_center_returns_200_with_correct_shape():
    client = TestClient(_build_app(_DATA, feature_enabled=True))
    resp = client.get(f"/clients/{CLIENT_ID}/command-center")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_locations"] == 3
    assert body["rollup"]["views"] == _EXPECTED_VIEWS
    assert body["rollup"]["calls"] == _EXPECTED_CALLS
    assert len(body["locations"]) == 3


def test_command_center_rollup_equals_location_sum():
    """Endpoint rollup must match the sum of its own ``locations`` array (E2E invariant)."""
    client = TestClient(_build_app(_DATA, feature_enabled=True))
    body = client.get(f"/clients/{CLIENT_ID}/command-center").json()
    locs = body["locations"]
    assert body["rollup"]["views"] == sum(loc["kpis"]["views"] for loc in locs)
    assert body["rollup"]["calls"] == sum(loc["kpis"]["calls"] for loc in locs)
    assert body["rollup"]["directions"] == sum(loc["kpis"]["directions"] for loc in locs)
    assert body["rollup"]["website_clicks"] == sum(loc["kpis"]["website_clicks"] for loc in locs)


def test_disabled_feature_returns_403_feature_disabled():
    """dashboard_multi_location off → 403 feature_disabled (PRD §7 D-6)."""
    client = TestClient(_build_app(_DATA, feature_enabled=False))
    resp = client.get(f"/clients/{CLIENT_ID}/command-center")
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"]["code"] == "feature_disabled"
    assert body["error"]["details"]["feature"] == MULTI_LOCATION_FEATURE
