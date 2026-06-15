"""P1D-3 acceptance: token health monitor (worker) + GET /connections/{id}/health.

Worker coverage:
- An expiring (within the warning window) token is flagged ``expiring`` and
  fires a ``token_expiring`` WARNING alert with a re-auth URL.
- A token with expiry still far in the future is untouched.
- A token with no expiry set is untouched.
- A ``disconnected`` token fires a ``token_disconnected`` CRITICAL alert.
- A session is committed after the sweep.
- An already-``expiring`` connection is not re-flagged or re-alerted.

Endpoint coverage:
- GET /connections/{id}/health returns the token_status, scopes, and a reauth_url.
- Cross-tenant access returns 404 (indistinguishable from not found).
- Unauthenticated returns 401.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.alerts import InMemoryAlertSink, SEVERITY_CRITICAL, SEVERITY_WARNING
from app.jobs.token_health import scan_connections
from app.models.connection import GbpConnection
from app.security.context import RequestContext, RoleAssignment
from tests.connections.fakes import build_env

TENANT = UUID("dd000000-0000-0000-0000-000000000001")
OTHER_TENANT = UUID("dd000000-0000-0000-0000-000000000002")
CLIENT = UUID("ee000000-0000-0000-0000-000000000001")

CLIENT_TENANTS = {CLIENT: TENANT}

_NOW_UTC = datetime.now(timezone.utc).replace(tzinfo=None)
_EXPIRING_SOON = _NOW_UTC + timedelta(days=3)    # within the default 7-day window
_EXPIRES_LATER = _NOW_UTC + timedelta(days=30)   # safe, outside the warning window


def _make_conn(**kwargs) -> GbpConnection:
    defaults = dict(
        id=uuid4(),
        client_id=CLIENT,
        connect_method="self_serve",
        token_ref="gbp/test/placeholder",
        scopes=["https://www.googleapis.com/auth/business.manage"],
        token_status="healthy",
        expires_at=None,
        agency_gbp_project_id=None,
    )
    defaults.update(kwargs)
    return GbpConnection(**defaults)


class FakeSession:
    """Minimal session-like object for the worker — no real DB required."""

    def __init__(self, connections: list[GbpConnection]) -> None:
        self._connections = connections
        self.committed = False

    def query(self, _model: type) -> "FakeSession":
        return self

    def all(self) -> list[GbpConnection]:
        return list(self._connections)

    def commit(self) -> None:
        self.committed = True


# ── worker: expiring token ────────────────────────────────────────────────────

def test_expiring_token_is_flagged_and_warning_alert_fired():
    conn = _make_conn(expires_at=_EXPIRING_SOON, token_status="healthy")
    sink = InMemoryAlertSink()

    result = scan_connections(FakeSession([conn]), sink)

    assert conn.token_status == "expiring", "status must be updated to expiring"
    assert result["expiring_flagged"] == 1
    assert result["disconnected_alerted"] == 0

    assert len(sink.alerts) == 1
    alert = sink.alerts[0]
    assert alert.kind == "token_expiring"
    assert alert.severity == SEVERITY_WARNING
    assert str(conn.id) == alert.context["connection_id"]
    assert "reauth" in alert.context["reauth_url"]


def test_healthy_token_not_near_expiry_is_untouched():
    conn = _make_conn(expires_at=_EXPIRES_LATER, token_status="healthy")
    sink = InMemoryAlertSink()

    result = scan_connections(FakeSession([conn]), sink)

    assert conn.token_status == "healthy"
    assert result["expiring_flagged"] == 0
    assert len(sink.alerts) == 0


def test_healthy_token_with_no_expiry_is_untouched():
    conn = _make_conn(expires_at=None, token_status="healthy")
    sink = InMemoryAlertSink()

    result = scan_connections(FakeSession([conn]), sink)

    assert conn.token_status == "healthy"
    assert len(sink.alerts) == 0


# ── worker: disconnected token ────────────────────────────────────────────────

def test_disconnected_token_fires_critical_alert():
    conn = _make_conn(token_status="disconnected", expires_at=None)
    sink = InMemoryAlertSink()

    result = scan_connections(FakeSession([conn]), sink)

    assert result["disconnected_alerted"] == 1
    assert result["expiring_flagged"] == 0

    assert len(sink.alerts) == 1
    alert = sink.alerts[0]
    assert alert.kind == "token_disconnected"
    assert alert.severity == SEVERITY_CRITICAL
    assert str(conn.id) == alert.context["connection_id"]
    assert "reauth" in alert.context["reauth_url"]


def test_session_is_committed_after_sweep():
    session = FakeSession([])
    scan_connections(session, InMemoryAlertSink())
    assert session.committed


def test_already_expiring_status_is_not_re_flagged():
    """A connection already in 'expiring' state must not be counted or re-alerted."""
    conn = _make_conn(expires_at=_EXPIRING_SOON, token_status="expiring")
    sink = InMemoryAlertSink()

    result = scan_connections(FakeSession([conn]), sink)

    assert result["expiring_flagged"] == 0
    assert len(sink.alerts) == 0


def test_mixed_connections_flagged_correctly():
    healthy_safe = _make_conn(expires_at=_EXPIRES_LATER, token_status="healthy")
    healthy_expiring = _make_conn(expires_at=_EXPIRING_SOON, token_status="healthy")
    disconnected = _make_conn(token_status="disconnected")
    already_expiring = _make_conn(expires_at=_EXPIRING_SOON, token_status="expiring")

    sink = InMemoryAlertSink()
    result = scan_connections(
        FakeSession([healthy_safe, healthy_expiring, disconnected, already_expiring]),
        sink,
    )

    assert result["expiring_flagged"] == 1
    assert result["disconnected_alerted"] == 1
    assert len(sink.alerts) == 2
    kinds = {a.kind for a in sink.alerts}
    assert kinds == {"token_expiring", "token_disconnected"}


# ── health endpoint ───────────────────────────────────────────────────────────

def _principal(role: str, tenant_id: UUID = TENANT) -> RequestContext:
    return RequestContext(
        user_id=uuid4(), tenant_id=tenant_id, roles=(RoleAssignment(role=role),)
    )


def test_health_endpoint_returns_status_and_reauth_url():
    env = build_env(CLIENT_TENANTS, _principal("account_manager"))
    conn = _make_conn(client_id=CLIENT, token_status="expiring", expires_at=_EXPIRING_SOON)
    env["store"].connections[conn.id] = conn

    resp = env["client"].get(f"/connections/{conn.id}/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_status"] == "expiring"
    assert body["connection_id"] == str(conn.id)
    assert "reauth" in body["reauth_url"]
    assert isinstance(body["scopes"], list)


def test_health_endpoint_healthy_connection_accessible_by_analyst():
    env = build_env(CLIENT_TENANTS, _principal("analyst"))
    conn = _make_conn(client_id=CLIENT, token_status="healthy", expires_at=_EXPIRES_LATER)
    env["store"].connections[conn.id] = conn

    resp = env["client"].get(f"/connections/{conn.id}/health")

    assert resp.status_code == 200
    assert resp.json()["token_status"] == "healthy"


def test_health_endpoint_disconnected_connection():
    env = build_env(CLIENT_TENANTS, _principal("account_manager"))
    conn = _make_conn(client_id=CLIENT, token_status="disconnected")
    env["store"].connections[conn.id] = conn

    resp = env["client"].get(f"/connections/{conn.id}/health")

    assert resp.status_code == 200
    assert resp.json()["token_status"] == "disconnected"


def test_health_endpoint_unknown_connection_is_404():
    env = build_env(CLIENT_TENANTS, _principal("account_manager"))

    resp = env["client"].get(f"/connections/{uuid4()}/health")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "connection_not_found"


def test_health_endpoint_cross_tenant_is_404():
    """A caller from another tenant sees the connection as non-existent."""
    env = build_env(CLIENT_TENANTS, _principal("account_manager", OTHER_TENANT))
    conn = _make_conn(client_id=CLIENT, token_status="healthy")
    env["store"].connections[conn.id] = conn

    resp = env["client"].get(f"/connections/{conn.id}/health")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "connection_not_found"


def test_health_endpoint_unauthenticated_401():
    env = build_env(CLIENT_TENANTS, principal=None)

    resp = env["client"].get(f"/connections/{uuid4()}/health")

    assert resp.status_code == 401
