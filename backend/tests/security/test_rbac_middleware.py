"""P1B-2: the RBAC dependency enforces capabilities over HTTP.

Builds a throwaway app whose routes are guarded by ``require(...)``, then drives
it as each of the five roles. A held capability → 200; a missing one → 403 with
the §1 error envelope; no principal → 401. The auth seam
(``get_request_context``) is overridden per role, exactly as P1B-1 will populate
it from a JWT.
"""
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.errors import install_error_handlers
from app.security.context import RequestContext, RoleAssignment
from app.security.deps import get_request_context, require

ROLES = ["super_admin", "agency_admin", "account_manager", "client_owner", "analyst"]
# Who may POST a review reply (an account_manager+ capability).
CAN_REPLY = {"super_admin", "agency_admin", "account_manager"}

CLIENT_A = UUID("11111111-1111-1111-1111-111111111111")


def build_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.post("/reviews/{review_id}/reply")
    def reply(review_id: str, ctx: RequestContext = Depends(require("reviews.reply"))):
        return {"ok": True, "actor": str(ctx.user_id)}

    @app.get("/reviews/{review_id}")
    def read_review(review_id: str, ctx: RequestContext = Depends(require("reviews.read"))):
        return {"ok": True}

    @app.post("/clients/{client_id}/reviews/reply")
    def scoped_reply(
        client_id: UUID,
        ctx: RequestContext = Depends(require("reviews.reply", scope_param="client_id")),
    ):
        return {"ok": True}

    return app


@pytest.fixture
def app() -> FastAPI:
    return build_app()


def as_role(app: FastAPI, role: str, **kw) -> None:
    """Make every request to ``app`` authenticate as a single-role principal."""
    principal = RequestContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        roles=(RoleAssignment(role=role, **kw),),
    )
    app.dependency_overrides[get_request_context] = lambda: principal


@pytest.mark.parametrize("role", ROLES)
def test_reply_capability_per_role(app, role):
    """reviews.reply: account_manager+ get 200, client_owner/analyst get 403."""
    as_role(app, role)
    resp = TestClient(app).post("/reviews/abc/reply")
    if role in CAN_REPLY:
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
    else:
        assert resp.status_code == 403


@pytest.mark.parametrize("role", ROLES)
def test_read_capability_allows_every_role(app, role):
    """reviews.read is the analyst+ tier — all five roles hold it."""
    as_role(app, role)
    resp = TestClient(app).get("/reviews/abc")
    assert resp.status_code == 200


def test_forbidden_uses_spec_error_envelope(app):
    as_role(app, "analyst")
    resp = TestClient(app).post("/reviews/abc/reply")
    assert resp.status_code == 403
    body = resp.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "forbidden"
    assert body["error"]["details"]["required_capability"] == "reviews.reply"


def test_unauthenticated_returns_401(app):
    """No principal configured → the auth seam raises 401, never an open door."""
    resp = TestClient(app).post("/reviews/abc/reply")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


def test_scope_out_of_scope_is_forbidden(app):
    """An account_manager scoped to client A is denied on a different client (RBAC-2)."""
    as_role(app, "account_manager", scope_type="client", scope_id=CLIENT_A)
    client = TestClient(app)
    assert client.post(f"/clients/{CLIENT_A}/reviews/reply").status_code == 200
    other_client = uuid4()
    assert client.post(f"/clients/{other_client}/reviews/reply").status_code == 403
