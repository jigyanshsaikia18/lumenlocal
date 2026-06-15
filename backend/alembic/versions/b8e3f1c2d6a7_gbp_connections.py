"""gbp_connections

OAuth bindings between a client and Google (P1D-1, DB schema §4):

* ``gbp_connections`` — one row per connection (self_serve / agency_proxy). The raw
  OAuth token is **never** stored here; only ``token_ref`` (a vault pointer) plus the
  non-secret ``scopes`` / ``expires_at`` health metadata. The table has no
  ``tenant_id`` of its own and is scoped transitively through ``client_id`` — the
  same trick ``geogrid_scans`` uses through ``location_id`` (revision 7f3c9d2e1a4b):
  the ``clients`` subquery is itself RLS-filtered for the app role, so a connection
  resolves only within the current tenant.

Revision ID: b8e3f1c2d6a7
Revises: a1f7c4d92e58
Create Date: 2026-06-15 15:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b8e3f1c2d6a7"
down_revision: Union[str, Sequence[str], None] = "a1f7c4d92e58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "lumen_app"


def upgrade() -> None:
    op.create_table(
        "gbp_connections",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("connect_method", sa.String(length=20), nullable=False),
        sa.Column("token_ref", sa.String(length=255), nullable=False),
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "token_status", sa.String(length=20), server_default=sa.text("'healthy'"), nullable=False
        ),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_gbp_connections_client_id", "gbp_connections", ["client_id"], unique=False
    )
    op.create_index(
        "ix_gbp_connections_expires_at", "gbp_connections", ["expires_at"], unique=False
    )

    # Runtime app role gets full DML; RLS constrains the rows (mirrors P1A-2 grants).
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON gbp_connections TO {APP_ROLE};")

    # RLS: transitive via clients (which is itself RLS-filtered for the app role).
    op.execute("ALTER TABLE gbp_connections ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE gbp_connections FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON gbp_connections
            USING (client_id IN (SELECT id FROM clients))
            WITH CHECK (client_id IN (SELECT id FROM clients));
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON gbp_connections;")
    op.execute("ALTER TABLE gbp_connections NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE gbp_connections DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_gbp_connections_expires_at", table_name="gbp_connections")
    op.drop_index("ix_gbp_connections_client_id", table_name="gbp_connections")
    op.drop_table("gbp_connections")
