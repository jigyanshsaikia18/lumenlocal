"""Seed a single demo tenant + agency-admin user so the hosted MVP demo is
loginable. NOT for production — this is the "click through the dashboards"
account for early agency demos.

Idempotent: re-running updates the demo user's password instead of duplicating.
Run inside the stack:

    docker compose -f docker-compose.prod.yml run --rm backend python -m scripts.seed_demo

Credentials (override via env): DEMO_EMAIL / DEMO_PASSWORD.
"""
from __future__ import annotations

import os
from uuid import uuid4

from sqlalchemy import text

from app.core.security import hash_password
from app.db.session import SessionLocal

DEMO_EMAIL = os.environ.get("DEMO_EMAIL", "demo@lumenlocal.app")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "demo-lumen-2026")
DEMO_COMPANY = "LumenLocal Demo Agency"


def seed() -> None:
    hashed = hash_password(DEMO_PASSWORD)

    with SessionLocal() as s:
        existing = s.execute(
            text("SELECT id, tenant_id FROM users WHERE email = :e"),
            {"e": DEMO_EMAIL},
        ).first()

        if existing is not None:
            s.execute(
                text("UPDATE users SET password_hash = :h, status = 'active' WHERE email = :e"),
                {"h": hashed, "e": DEMO_EMAIL},
            )
            s.commit()
            print(f"Updated existing demo user: {DEMO_EMAIL}")
            return

        tenant_id = uuid4()
        user_id = uuid4()
        role_id = uuid4()

        s.execute(
            text("INSERT INTO tenants (id, company_name) VALUES (:id, :n)"),
            {"id": tenant_id, "n": DEMO_COMPANY},
        )
        s.execute(
            text(
                "INSERT INTO users (id, tenant_id, email, password_hash, status) "
                "VALUES (:id, :t, :e, :h, 'active')"
            ),
            {"id": user_id, "t": tenant_id, "e": DEMO_EMAIL, "h": hashed},
        )
        s.execute(
            text(
                "INSERT INTO user_roles (id, user_id, role, scope_type) "
                "VALUES (:id, :uid, 'agency_admin', 'tenant')"
            ),
            {"id": role_id, "uid": user_id},
        )
        s.commit()

    print("Seeded demo account:")
    print(f"  email:    {DEMO_EMAIL}")
    print(f"  password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    seed()
