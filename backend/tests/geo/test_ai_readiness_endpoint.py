"""P2C-3: GET /locations/{id}/ai-readiness — chain + shape (API spec §6, §12).

Mirrors the command-center endpoint test: the audit service and entitlement
service are overridden (no Postgres), and we assert the response shape plus the
``403 feature_disabled`` gate. The audit *content* is covered exhaustively by the
pure-engine tests in ``test_ai_readiness.py``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.ai_readiness import (
    AI_READINESS_FEATURE,
    get_ai_readiness_service,
    router,
)
from app.core.errors import install_error_handlers
from app.entitlements.cache import entitlement_cache
from app.entitlements.gateway import get_entitlement_service
from app.entitlements.repository import EntitlementService
from app.geo.ai_readiness import audit_ai_readiness
from app.security.context import RequestContext, RoleAssignment
from app.security.deps import get_request_context
from tests.entitlements.fakes import FakeEntitlementBackend, feat

CLIENT_ID = UUID("c0000000-0000-0000-0000-000000000001")
LOCATION_ID = UUID("10000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 6, 16, tzinfo=timezone.utc)

_FEATURES = [feat(AI_READINESS_FEATURE, default=True)]

# A profile with two clear gaps → at least one recommendation to assert against.
_PROFILE = {
    "primary_category": None,
    "nap_consistency": {"directories_checked": 5, "mismatches": 1},
}


@pytest.fixture(autouse=True)
def _clear_entitlement_cache():
    entitlement_cache.clear()
    yield
    entitlement_cache.clear()


def _principal() -> RequestContext:
    # analyst holds ai_readiness.read (read bundle) — the documented min role.
    return RequestContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        roles=(RoleAssignment(role="analyst"),),
    )


class _FakeService:
    def get_report(self, tenant_id, location_id, now=None):
        return audit_ai_readiness(_PROFILE, now=NOW), NOW


def _build_app(*, feature_enabled: bool) -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(router)

    client_overrides = (
        {} if feature_enabled else {CLIENT_ID: {AI_READINESS_FEATURE: False}}
    )
    backend = FakeEntitlementBackend(
        _FEATURES,
        client=client_overrides,
        location_client={LOCATION_ID: CLIENT_ID},
    )

    app.dependency_overrides[get_request_context] = _principal
    app.dependency_overrides[get_entitlement_service] = lambda: EntitlementService(backend)
    app.dependency_overrides[get_ai_readiness_service] = lambda: _FakeService()
    return app


def test_ai_readiness_returns_200_with_audit_shape():
    client = TestClient(_build_app(feature_enabled=True))
    resp = client.get(f"/locations/{LOCATION_ID}/ai-readiness")
    assert resp.status_code == 200
    body = resp.json()

    assert body["location_id"] == str(LOCATION_ID)
    assert 0 <= body["overall_score"] <= 100
    # All eight GEO-7 signals are reported.
    assert len(body["signals"]) == 8
    # Profile has gaps → at least one prioritized action, top one is the heaviest.
    assert body["recommendations"], "expected at least one recommendation"
    assert body["recommendations"][0]["signal"] == "category_specificity"
    assert body["recommendations"][0]["priority"] == "high"


def test_recommendations_are_impact_ordered_in_response():
    client = TestClient(_build_app(feature_enabled=True))
    recs = client.get(f"/locations/{LOCATION_ID}/ai-readiness").json()["recommendations"]
    impacts = [r["impact_points"] for r in recs]
    assert impacts == sorted(impacts, reverse=True)


def test_disabled_feature_returns_403_feature_disabled():
    """ai_readiness off for the client → 403 feature_disabled (§12 step 3)."""
    client = TestClient(_build_app(feature_enabled=False))
    resp = client.get(f"/locations/{LOCATION_ID}/ai-readiness")
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"]["code"] == "feature_disabled"
    assert body["error"]["details"]["feature"] == AI_READINESS_FEATURE
