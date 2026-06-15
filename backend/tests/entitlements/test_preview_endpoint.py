"""P1C-3 acceptance: GET /clients/{id}/preview returns the resolver's output.

Verifies:
- The preview response matches the resolver output for the same client.
- The role query param is echoed back; default is ``client_owner``.
- After a client-level override, the preview reflects the new state.
"""
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.deps import get_db
from app.api.v1.entitlements import get_entitlement_admin, router
from app.audit.log import InMemoryAuditLogSink
from app.core.errors import install_error_handlers
from app.entitlements.admin import EntitlementAdminService
from app.entitlements.gateway import get_entitlement_service
from app.entitlements.repository import EntitlementService
from app.security.context import RequestContext, RoleAssignment
from app.security.deps import get_request_context
from tests.entitlements.fakes import FakeEntitlementBackend, feat

CLIENT_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
FEATURES = [feat("geogrid", default=True), feat("review_inbox", default=False)]


class DummySession:
    def commit(self) -> None:
        pass


@pytest.fixture()
def env():
    """App wired with shared in-memory backend (read+write) so toggles are visible."""
    backend = FakeEntitlementBackend(FEATURES)
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

    return TestClient(app)


def test_preview_matches_resolver_output(env):
    """Preview and /entitlements/resolve return the same feature set for the same client."""
    resolve_body = env.get(f"/entitlements/resolve?client_id={CLIENT_A}").json()
    preview_body = env.get(f"/clients/{CLIENT_A}/preview?role=client_owner").json()

    resolve_by_key = {f["key"]: f for f in resolve_body["features"]}
    preview_by_key = {f["key"]: f for f in preview_body["features"]}
    assert resolve_by_key == preview_by_key


def test_preview_metadata(env):
    """Preview echoes client_id and role, and covers all registered features."""
    preview = env.get(f"/clients/{CLIENT_A}/preview?role=client_owner").json()
    assert preview["client_id"] == str(CLIENT_A)
    assert preview["role"] == "client_owner"
    assert len(preview["features"]) == len(FEATURES)


def test_preview_default_role_is_client_owner(env):
    """When ?role is omitted the response defaults to client_owner."""
    preview = env.get(f"/clients/{CLIENT_A}/preview").json()
    assert preview["role"] == "client_owner"


def test_preview_reflects_client_override(env):
    """After toggling geogrid off for the client, the preview shows it disabled."""
    env.put(f"/clients/{CLIENT_A}/features/geogrid", json={"state": False})

    preview = env.get(f"/clients/{CLIENT_A}/preview?role=client_owner").json()
    by_key = {f["key"]: f for f in preview["features"]}
    assert by_key["geogrid"]["enabled"] is False
    assert by_key["geogrid"]["source"] == "client"


def test_preview_role_label_does_not_filter_features(env):
    """Different role values return the same feature set (role is informational only)."""
    owner_preview = env.get(f"/clients/{CLIENT_A}/preview?role=client_owner").json()
    analyst_preview = env.get(f"/clients/{CLIENT_A}/preview?role=analyst").json()

    owner_by_key = {f["key"]: f for f in owner_preview["features"]}
    analyst_by_key = {f["key"]: f for f in analyst_preview["features"]}
    assert owner_by_key == analyst_by_key
