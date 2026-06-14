"""tenant_isolation_rls

Enforces tenant isolation in the database (P1A-2), not by application convention:

* Creates a non-superuser application role ``lumen_app`` (NOBYPASSRLS). The app
  connects as this role at runtime; row-level security therefore applies to it.
  The migration/admin role (``lumen``) stays a superuser and is exempt.
* Enables ROW LEVEL SECURITY (+ FORCE) on every tenant-scoped table and adds a
  policy keyed to the ``app.current_tenant`` GUC the app sets per transaction.
* Fail-closed: with no tenant context, ``current_setting(..., true)`` is NULL and
  ``tenant_id = NULL`` matches no rows.

Revision ID: 9029056a7245
Revises: 955e834c7a9d
Create Date: 2026-06-14 13:00:50.957616
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9029056a7245"
down_revision: Union[str, Sequence[str], None] = "955e834c7a9d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "lumen_app"
# Dev-tier password only; production provisions this role via infra/secrets, not here.
APP_ROLE_PASSWORD = "lumen_app_dev_password"

# Tables scoped directly by a tenant_id column.
TENANT_ID_TABLES = ("clients", "users")

# The active tenant, read from the per-transaction GUC. NULLIF(..., '') is essential:
# on a pooled connection a custom GUC reverts to an EMPTY STRING (not NULL) after a
# transaction that set it, and ''::uuid would raise. Collapsing '' -> NULL makes a
# context-less query deterministically fail closed (match no rows) instead of erroring.
TENANT_EXPR = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"


def upgrade() -> None:
    # --- 1. Application role (idempotent), explicitly NOT a superuser / NOBYPASSRLS ---
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_ROLE_PASSWORD}'
                    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
            END IF;
        END
        $$;
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE};")
    # Global reference data: read-only.
    op.execute(f"GRANT SELECT ON plans, role_permissions TO {APP_ROLE};")
    # Tenant-scoped data: full DML (RLS constrains which rows).
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON tenants, clients, users, user_roles "
        f"TO {APP_ROLE};"
    )

    # --- 2. RLS on tenants (scoped by its own id) ---
    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE tenants FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON tenants
            USING (id = {TENANT_EXPR})
            WITH CHECK (id = {TENANT_EXPR});
        """
    )

    # --- 3. RLS on tables with a tenant_id column ---
    for table in TENANT_ID_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (tenant_id = {TENANT_EXPR})
                WITH CHECK (tenant_id = {TENANT_EXPR});
            """
        )

    # --- 4. RLS on user_roles (no tenant_id; scoped transitively via users) ---
    # The subquery against users is itself RLS-filtered for the app role, so this
    # resolves to exactly the current tenant's users.
    op.execute("ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE user_roles FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON user_roles
            USING (user_id IN (SELECT id FROM users))
            WITH CHECK (user_id IN (SELECT id FROM users));
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON user_roles;")
    op.execute("ALTER TABLE user_roles NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE user_roles DISABLE ROW LEVEL SECURITY;")

    for table in TENANT_ID_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenants;")
    op.execute("ALTER TABLE tenants NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY;")

    # Remove all privileges granted to the app role in this database, then drop it.
    op.execute(f"DROP OWNED BY {APP_ROLE};")
    op.execute(f"DROP ROLE IF EXISTS {APP_ROLE};")
