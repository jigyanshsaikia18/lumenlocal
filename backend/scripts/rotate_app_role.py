"""Set the RLS-scoped ``lumen_app`` role's password to match APP_DB_PASSWORD.

The tenant_isolation_rls migration CREATEs the role with a dev-tier password only
on first run (idempotent), so it never rotates an existing role. This runs right
after `alembic upgrade head` using the superuser DATABASE_URL connection and makes
the app role's password match what the backend connects with — letting a public
deploy use a strong, env-supplied password instead of the baked-in dev default.

No-op (with a notice) when APP_DB_PASSWORD is unset, so local dev is unaffected.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine, text

ROLE = "lumen_app"


def rotate() -> None:
    password = os.environ.get("APP_DB_PASSWORD")
    if not password:
        print("APP_DB_PASSWORD not set — leaving lumen_app password unchanged.")
        return

    # Superuser connection (migrations/admin). ALTER ROLE requires this privilege.
    url = os.environ["DATABASE_URL"]
    engine = create_engine(url)
    with engine.begin() as conn:
        # ALTER ROLE is a utility statement and won't accept a bind parameter for the
        # password, and a DO block can't take parameters either. So stash the value in
        # a transaction-local GUC (the same mechanism RLS uses for app.current_tenant),
        # then build the statement server-side with format(%L) to escape it safely.
        conn.execute(text("SELECT set_config('lumen.app_role_pw', :pw, true)"), {"pw": password})
        conn.execute(
            text(
                "DO $$ BEGIN "
                f"EXECUTE format('ALTER ROLE {ROLE} PASSWORD %L', "
                "current_setting('lumen.app_role_pw')); "
                "END $$;"
            )
        )
    print(f"Rotated {ROLE} password to APP_DB_PASSWORD.")


if __name__ == "__main__":
    rotate()
