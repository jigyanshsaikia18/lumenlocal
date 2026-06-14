"""entitlement_tables

Feature-toggle engine tables (P1C-1, DB schema §3): the ``features`` registry and
the three per-scope override tables. Resolution precedence is computed in
``app.entitlements`` (location > client > plan > default).

Grants SELECT/DML on these tables to the runtime ``lumen_app`` role, mirroring the
P1A-2 grant model so the resolver can read them when connected as that role.

Note: these tables are keyed by ``scope_id`` with no ``tenant_id`` column (per the
schema), so the P1A-2 RLS tenant policies do not cover them. Tenant scoping of
``client_features`` / ``location_features`` is a documented security follow-up.

Revision ID: c4e1a7b2f9d3
Revises: 9029056a7245
Create Date: 2026-06-14 14:05:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c4e1a7b2f9d3"
down_revision: Union[str, Sequence[str], None] = "9029056a7245"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OVERRIDE_TABLES = ("plan_features", "client_features", "location_features")
APP_ROLE = "lumen_app"


def upgrade() -> None:
    op.create_table(
        "features",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "dependencies",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "default_state", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.PrimaryKeyConstraint("key"),
    )

    for table in OVERRIDE_TABLES:
        op.create_table(
            table,
            sa.Column(
                "id",
                sa.UUID(),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("scope_id", sa.UUID(), nullable=False),
            sa.Column("feature_key", sa.String(length=80), nullable=False),
            sa.Column("state", sa.Boolean(), nullable=False),
            sa.Column("set_by", sa.UUID(), nullable=True),
            sa.Column(
                "set_at",
                sa.TIMESTAMP(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["feature_key"], ["features.key"]),
            sa.ForeignKeyConstraint(["set_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(f"ix_{table}_scope_id", table, ["scope_id"], unique=False)

    # Runtime app role reads/writes these tables (mirrors P1A-2 grants).
    op.execute(f"GRANT SELECT ON features TO {APP_ROLE};")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        f"plan_features, client_features, location_features TO {APP_ROLE};"
    )


def downgrade() -> None:
    for table in reversed(OVERRIDE_TABLES):
        op.drop_index(f"ix_{table}_scope_id", table_name=table)
        op.drop_table(table)
    op.drop_table("features")
