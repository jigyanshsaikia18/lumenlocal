"""audit_log

The platform-wide, immutable audit trail (DB schema §7, RBAC-5). Introduced with
P1C-2 so entitlement toggles are recorded; the read API over it is P1E-3.

Immutability is enforced at the **database** level, not by convention (CLAUDE.md
hard rule; PRD §11.1 item 4):

* the runtime ``lumen_app`` role is granted only SELECT + INSERT (never UPDATE/DELETE);
* UPDATE/DELETE/TRUNCATE are REVOKEd from PUBLIC as defence-in-depth; and
* a ``BEFORE UPDATE OR DELETE`` trigger raises, so even the table owner (the
  migration superuser, which bypasses grants and RLS) cannot mutate a row.

Tenant-scoped, so it gets row-level security on ``tenant_id`` matching the P1A-2
pattern (revision 9029056a7245).

Revision ID: e2c5f9a4b173
Revises: f3a9c1e8b042
Create Date: 2026-06-15 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e2c5f9a4b173"
down_revision: Union[str, Sequence[str], None] = "f3a9c1e8b042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "lumen_app"

# Same fail-closed tenant expression as the P1A-2 RLS migration.
TENANT_EXPR = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=True),
        sa.Column("target_id", sa.UUID(), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_tenant_id", "audit_log", ["tenant_id"], unique=False)
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"], unique=False)

    # --- grants: append-only for the runtime role -----------------------------
    op.execute(f"GRANT SELECT, INSERT ON audit_log TO {APP_ROLE};")
    # Defence-in-depth: no one gets UPDATE/DELETE/TRUNCATE via grants.
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM PUBLIC;")
    op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM {APP_ROLE};")

    # --- immutability trigger: blocks UPDATE/DELETE even for the table owner ---
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_log_reject_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only: % is not permitted', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_immutable
            BEFORE UPDATE OR DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_reject_mutation();
        """
    )

    # --- RLS: scope rows to the request's tenant ------------------------------
    op.execute("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON audit_log
            USING (tenant_id = {TENANT_EXPR})
            WITH CHECK (tenant_id = {TENANT_EXPR});
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON audit_log;")
    op.execute("ALTER TABLE audit_log NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE audit_log DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP TRIGGER IF EXISTS audit_log_immutable ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS audit_log_reject_mutation();")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_tenant_id", table_name="audit_log")
    op.drop_table("audit_log")
