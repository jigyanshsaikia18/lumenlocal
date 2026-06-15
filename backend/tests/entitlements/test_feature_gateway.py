"""P1C-2: the gateway returns 403 feature_disabled for a toggled-off feature.

Drives a throwaway app whose route is guarded by ``require_feature`` (the same way
P1B-2 tested ``require``). The auth seam and the entitlement service are overridden;
no Postgres. A disabled feature for client A → 403; the same feature on for client B
→ 200 — proving the gate is per-client (PRD §5.3).
"""
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.errors import install_error_handlers
from app.entitlements.gateway import get_entitlement_service, require_feature
from app.entitlements.repository import EntitlementService
from app.security.context import RequestContext, RoleAssignment
from app.security.deps import get_request_context
from tests.entitlements.fakes import FakeEntitlementBackend, feat

CLIENT_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CLIENT_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

FEATURES = [feat("geogrid", default=True), feat("review_inbox", default=False)]


def build_app(backend: FakeEntitlementBackend) -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/clients/{client_id}/geogrid")
    def geogrid_view(
        client_id: UUID,
        ctx: RequestContext = Depends(
            require_feature("geogrid", "geogrid.read", client_param="client_id")
        ),
    ):
        return {"ok": True}

    # account_manager, tenant-wide → holds geogrid.read on any client.
    principal = RequestContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        roles=(RoleAssignment(role="account_manager"),),
    )
    app.dependency_overrides[get_request_context] = lambda: principal
    app.dependency_overrides[get_entitlement_service] = lambda: EntitlementService(backend)
    return app


def test_disabled_feature_returns_403_for_that_client_only():
    # geogrid disabled for A (client override), default-on for B.
    backend = FakeEntitlementBackend(FEATURES, client={CLIENT_A: {"geogrid": False}})
    client = TestClient(build_app(backend))

    resp_a = client.get(f"/clients/{CLIENT_A}/geogrid")
    assert resp_a.status_code == 403
    body = resp_a.json()
    assert body["error"]["code"] == "feature_disabled"
    assert body["error"]["details"]["feature"] == "geogrid"

    resp_b = client.get(f"/clients/{CLIENT_B}/geogrid")
    assert resp_b.status_code == 200
    assert resp_b.json() == {"ok": True}


def test_enabled_feature_passes_through():
    backend = FakeEntitlementBackend(FEATURES)  # geogrid default-on for everyone
    client = TestClient(build_app(backend))
    assert client.get(f"/clients/{CLIENT_A}/geogrid").status_code == 200


def test_dependency_forced_off_reads_as_disabled():
    """A feature whose prerequisite is off resolves off → 403 (FT-4 via the gate)."""
    features = [feat("review_inbox", default=False), feat("ai_writer", deps=("review_inbox",), default=True)]
    backend = FakeEntitlementBackend(features)

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/clients/{client_id}/ai-writer")
    def ai_writer(
        client_id: UUID,
        ctx: RequestContext = Depends(
            require_feature("ai_writer", "geogrid.read", client_param="client_id")
        ),
    ):
        return {"ok": True}

    principal = RequestContext(
        user_id=uuid4(), tenant_id=uuid4(), roles=(RoleAssignment(role="account_manager"),)
    )
    app.dependency_overrides[get_request_context] = lambda: principal
    app.dependency_overrides[get_entitlement_service] = lambda: EntitlementService(backend)

    resp = TestClient(app).get(f"/clients/{CLIENT_A}/ai-writer")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "feature_disabled"


def test_missing_capability_is_403_forbidden_before_entitlement():
    """RBAC (step 2) runs first: no capability → 403 forbidden, not feature_disabled."""
    backend = FakeEntitlementBackend(FEATURES)

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/clients/{client_id}/admin-only")
    def admin_only(
        client_id: UUID,
        ctx: RequestContext = Depends(
            require_feature("geogrid", "tenants.create", client_param="client_id")
        ),
    ):
        return {"ok": True}

    # analyst lacks tenants.create (a super_admin capability).
    principal = RequestContext(
        user_id=uuid4(), tenant_id=uuid4(), roles=(RoleAssignment(role="analyst"),)
    )
    app.dependency_overrides[get_request_context] = lambda: principal
    app.dependency_overrides[get_entitlement_service] = lambda: EntitlementService(backend)

    resp = TestClient(app).get(f"/clients/{CLIENT_A}/admin-only")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"
