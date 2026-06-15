"""P1E-3: audit_log UPDATE/DELETE rejected at the DB level (Postgres required).

Verifies that the ``audit_log_immutable`` BEFORE trigger raises for any UPDATE
or DELETE attempt, even when running as the privileged superuser session.  This
confirms immutability is enforced at the database level, not merely by
convention or by the application-role grants.

The conftest ``_migrate_to_head`` session fixture ensures the migration (and
therefore the trigger) is applied before this module runs.  Tests are skipped
if Postgres is unreachable.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import SessionLocal


def _open_session():
    """Open a privileged session; return ``None`` if Postgres is unreachable."""
    try:
        session = SessionLocal()
        session.execute(text("SELECT 1"))
        return session
    except Exception:  # noqa: BLE001
        return None


@pytest.fixture()
def db():
    """Fresh privileged session per test; skipped when Postgres is unavailable."""
    session = _open_session()
    if session is None:
        pytest.skip("Postgres unreachable — skipping immutability integration tests")
    yield session
    try:
        session.rollback()
    except Exception:  # noqa: BLE001
        pass
    session.close()


def _insert_row(db) -> object:
    """Insert a sentinel audit_log row; return its server-generated id."""
    tenant_id = uuid4()
    # Superuser session bypasses RLS and role grants — insert goes through.
    # Let the server generate the id via RETURNING so no ::uuid cast is needed.
    row_id = db.execute(
        text(
            "INSERT INTO audit_log (tenant_id, action) "
            "VALUES (:tid, 'test.immutability') RETURNING id"
        ),
        {"tid": tenant_id},
    ).scalar_one()
    db.commit()
    return row_id


def test_update_on_audit_log_is_rejected(db):
    """BEFORE UPDATE trigger raises for any row mutation, even from the superuser."""
    row_id = _insert_row(db)
    with pytest.raises(SQLAlchemyError, match="append-only"):
        db.execute(
            text("UPDATE audit_log SET action = 'mutated' WHERE id = :id"),
            {"id": row_id},
        )
        db.commit()
    db.rollback()


def test_delete_on_audit_log_is_rejected(db):
    """BEFORE DELETE trigger raises for any row deletion, even from the superuser."""
    row_id = _insert_row(db)
    with pytest.raises(SQLAlchemyError, match="append-only"):
        db.execute(
            text("DELETE FROM audit_log WHERE id = :id"),
            {"id": row_id},
        )
        db.commit()
    db.rollback()
