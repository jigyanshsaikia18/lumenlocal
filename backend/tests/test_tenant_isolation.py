"""P1A-2 acceptance: row-level security makes cross-tenant reads impossible.

Seeding is done as the superuser (bypasses RLS) so both tenants' rows exist.
Assertions run through the non-superuser app role (lumen_app), which IS subject
to RLS, proving isolation is enforced by Postgres — not by application convention.
"""
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.session import AppSessionLocal, SessionLocal, tenant_session


@pytest.fixture
def two_tenants():
    """Seed tenant A and tenant B, each with one client and one user (as superuser)."""
    a, b = uuid4(), uuid4()
    client_a, client_b = uuid4(), uuid4()
    user_a, user_b = uuid4(), uuid4()
    with SessionLocal() as s:
        for tid, cid, uid, tag in [
            (a, client_a, user_a, "a"),
            (b, client_b, user_b, "b"),
        ]:
            s.execute(
                text("INSERT INTO tenants (id, company_name) VALUES (:id, :n)"),
                {"id": tid, "n": f"Tenant {tag}"},
            )
            s.execute(
                text("INSERT INTO clients (id, tenant_id, name) VALUES (:id, :t, :n)"),
                {"id": cid, "t": tid, "n": f"Client {tag}"},
            )
            s.execute(
                text("INSERT INTO users (id, tenant_id, email) VALUES (:id, :t, :e)"),
                {"id": uid, "t": tid, "e": f"user-{cid}@example.com"},
            )
        s.commit()
    yield {
        "a": a,
        "b": b,
        "client_a": client_a,
        "client_b": client_b,
        "user_a": user_a,
        "user_b": user_b,
    }
    with SessionLocal() as s:  # teardown (superuser bypasses RLS)
        s.execute(
            text("DELETE FROM users WHERE id IN (:x, :y)"), {"x": user_a, "y": user_b}
        )
        s.execute(
            text("DELETE FROM clients WHERE id IN (:x, :y)"),
            {"x": client_a, "y": client_b},
        )
        s.execute(text("DELETE FROM tenants WHERE id IN (:x, :y)"), {"x": a, "y": b})
        s.commit()


def _ids(session, table):
    return {r[0] for r in session.execute(text(f"SELECT id FROM {table}"))}


def test_tenant_a_sees_only_its_own_rows(two_tenants):
    t = two_tenants
    with tenant_session(t["a"]) as s:
        assert _ids(s, "clients") == {t["client_a"]}
        assert _ids(s, "users") == {t["user_a"]}
        assert _ids(s, "tenants") == {t["a"]}  # can't even see tenant B exists
        assert t["client_b"] not in _ids(s, "clients")


def test_tenant_b_sees_only_its_own_rows(two_tenants):
    t = two_tenants
    with tenant_session(t["b"]) as s:
        assert _ids(s, "clients") == {t["client_b"]}
        assert t["client_a"] not in _ids(s, "clients")
        assert t["a"] not in _ids(s, "tenants")


def test_no_tenant_context_is_fail_closed(two_tenants):
    """No app.current_tenant set → zero rows, never a leak."""
    with AppSessionLocal() as s:
        assert s.execute(text("SELECT count(*) FROM clients")).scalar() == 0
        assert s.execute(text("SELECT count(*) FROM users")).scalar() == 0


def test_cannot_insert_row_for_another_tenant(two_tenants):
    """WITH CHECK blocks writing a row stamped with someone else's tenant_id."""
    t = two_tenants
    with pytest.raises(Exception, match="row-level security"):
        with tenant_session(t["a"]) as s:
            s.execute(
                text("INSERT INTO clients (id, tenant_id, name) VALUES (:id, :t, 'x')"),
                {"id": uuid4(), "t": t["b"]},
            )


def test_cannot_move_row_into_another_tenant(two_tenants):
    t = two_tenants
    with pytest.raises(Exception, match="row-level security"):
        with tenant_session(t["a"]) as s:
            s.execute(
                text("UPDATE clients SET tenant_id = :b WHERE id = :id"),
                {"b": t["b"], "id": t["client_a"]},
            )


def test_app_role_cannot_bypass_rls(two_tenants):
    """Guards the security premise: the runtime role is not a superuser / BYPASSRLS."""
    with AppSessionLocal() as s:
        row = s.execute(
            text(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )
        ).one()
        assert row.rolsuper is False
        assert row.rolbypassrls is False
