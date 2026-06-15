"""P1C-2 acceptance: disabling a feature for one client is enforced + audited.

The ticket's test, end-to-end over HTTP with no Postgres:

* ``PUT /clients/{A}/features/geogrid {state:false}`` disables geogrid for client A;
* a geogrid-gated route then returns ``403 feature_disabled`` for A but ``200`` for
  client B (the change is per-client, PRD §5.3); and
* the toggle is written to ``audit_log`` (RBAC-5 / FT-6) with before/after state.

The override write and resolve share one in-memory backend, the audit sink is
in-memory, and the toggle invalidates the process cache so the gated route sees the
new state immediately (FT-2).
"""
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.v1.deps import get_db
from app.api.v1.entitlements import get_entitlement_admin, router
from app.audit.log import InMemoryAuditLogSink
from app.core.errors import install_error_handlers
from app.entitlements.admin import ACTION_SET_OVERRIDE, EntitlementAdminService
from app.entitlements.gateway import get_entitlement_service, require_feature
from app.entitlements.repository import EntitlementService
from app.security.context import RequestContext, RoleAssignment
from app.security.deps import get_request_context
from tests.entitlements.fakes import FakeEntitlementBackend, feat

CLIENT_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CLIENT_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TENANT = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

FEATURES = [feat("geogrid", default=True), feat("review_inbox", default=False)]


class DummySession:
    """Stands in for the request DB session; commit is a no-op (no real DB)."""

    def commit(self) -> None:  # pragma: no cover - trivial
        pass


@pytest.fixture()
def env():
    """Wire a test app sharing one backend (read+write) and one audit sink."""
    backend = FakeEntitlementBackend(FEATURES)
    sink = InMemoryAuditLogSink()
    service = EntitlementService(backend)
    admin = EntitlementAdminService(backend, service, sink)

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(router)

    # A geogrid-gated business route, to prove the toggle is *enforced*, not just stored.
    @app.get("/clients/{client_id}/geogrid-data")
    def geogrid_data(
        client_id: UUID,
        ctx: RequestContext = Depends(
            require_feature("geogrid", "geogrid.read", client_param="client_id")
        ),
    ):
        return {"ok": True}

    principal = RequestContext(
        user_id=uuid4(), tenant_id=TENANT, roles=(RoleAssignment(role="agency_admin"),)
    )
    app.dependency_overrides[get_request_context] = lambda: principal
    app.dependency_overrides[get_entitlement_service] = lambda: service
    app.dependency_overrides[get_entitlement_admin] = lambda: admin
    app.dependency_overrides[get_db] = lambda: DummySession()

    return {"client": TestClient(app), "sink": sink, "principal": principal}


def _geogrid_enabled(resolve_body) -> bool:
    by_key = {f["key"]: f for f in resolve_body["features"]}
    return by_key["geogrid"]["enabled"]


def test_disable_feature_for_one_client_only(env):
    client = env["client"]

    # Baseline: geogrid on for both clients (platform default).
    assert _geogrid_enabled(client.get(f"/entitlements/resolve?client_id={CLIENT_A}").json())
    assert _geogrid_enabled(client.get(f"/entitlements/resolve?client_id={CLIENT_B}").json())

    # Disable geogrid for client A.
    put = client.put(f"/clients/{CLIENT_A}/features/geogrid", json={"state": False})
    assert put.status_code == 200
    assert put.json()["state"] is False
    assert put.json()["previous_state"] is None  # no prior override → was inherited

    # Resolve reflects the change for A but not B.
    a_body = client.get(f"/entitlements/resolve?client_id={CLIENT_A}").json()
    b_body = client.get(f"/entitlements/resolve?client_id={CLIENT_B}").json()
    assert _geogrid_enabled(a_body) is False
    assert _geogrid_enabled(b_body) is True

    # The gated route is now 403 for A, still 200 for B.
    assert client.get(f"/clients/{CLIENT_A}/geogrid-data").status_code == 403
    assert (
        client.get(f"/clients/{CLIENT_A}/geogrid-data").json()["error"]["code"]
        == "feature_disabled"
    )
    assert client.get(f"/clients/{CLIENT_B}/geogrid-data").status_code == 200


def test_toggle_is_audit_logged(env):
    client, sink, principal = env["client"], env["sink"], env["principal"]

    client.put(f"/clients/{CLIENT_A}/features/geogrid", json={"state": False})

    assert len(sink.entries) == 1
    entry = sink.entries[0]
    assert entry.action == ACTION_SET_OVERRIDE
    assert entry.tenant_id == TENANT
    assert entry.actor_user_id == principal.user_id
    assert entry.target_type == "client"
    assert entry.target_id == CLIENT_A
    assert entry.before == {"feature_key": "geogrid", "state": None}
    assert entry.after == {"feature_key": "geogrid", "state": False}


def test_unknown_feature_is_404(env):
    resp = env["client"].put(f"/clients/{CLIENT_A}/features/not_a_feature", json={"state": True})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "feature_not_found"


def test_enable_with_missing_dependency_is_409(env):
    """Enabling ai_writer while review_inbox is off is rejected (FT-4), not forced off."""
    backend = FakeEntitlementBackend(
        [feat("review_inbox", default=False), feat("ai_writer", deps=("review_inbox",))]
    )
    sink = InMemoryAuditLogSink()
    service = EntitlementService(backend)
    admin = EntitlementAdminService(backend, service, sink)

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(router)
    principal = RequestContext(
        user_id=uuid4(), tenant_id=TENANT, roles=(RoleAssignment(role="agency_admin"),)
    )
    app.dependency_overrides[get_request_context] = lambda: principal
    app.dependency_overrides[get_entitlement_service] = lambda: service
    app.dependency_overrides[get_entitlement_admin] = lambda: admin
    app.dependency_overrides[get_db] = lambda: DummySession()

    resp = TestClient(app).put(f"/clients/{CLIENT_A}/features/ai_writer", json={"state": True})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "dependency_not_enabled"
    assert sink.entries == []  # rejected before any write/audit
