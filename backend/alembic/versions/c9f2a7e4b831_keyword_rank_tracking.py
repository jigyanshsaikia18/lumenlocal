"""keyword_rank_tracking

Adds keyword rank tracking tables (P2B-2):

* ``keyword_rank_schedules`` — which (keyword, device, interval) to track for a
  location, with a ``last_run_at`` timestamp the dispatch sweep uses to determine
  due rows.
* ``keyword_rank_results`` — one scan result row per (location, keyword, device)
  run: map-pack rank, organic rank, and run timestamp for trend charting.

Both tables are tenant-scoped transitively through ``location_id`` (same RLS
pattern as ``geogrid_scans`` in revision 7f3c9d2e1a4b): the ``locations``
subquery is itself RLS-filtered for the app role, so a scan result is only ever
visible to the tenant that owns the location.

The ``usage_quotas`` / ``usage_counters`` tables already support arbitrary metric
names (VARCHAR(40)); the new ``keyword_rank_scans`` metric key is added to the
application's ``METERED_METRICS`` set in ``app.quotas.service``.

Revision ID: c9f2a7e4b831
Revises: b8e3f1c2d6a7
Create Date: 2026-06-16 09:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9f2a7e4b831"
down_revision: Union[str, Sequence[str], None] = "b8e3f1c2d6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "lumen_app"

# Same fail-closed tenant expression as all prior RLS migrations.
TENANT_EXPR = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"


def upgrade() -> None:
    # ------------------------------------------------------------------ tables
    op.create_table(
        "keyword_rank_schedules",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("keyword", sa.String(length=255), nullable=False),
        sa.Column(
            "device",
            sa.String(length=20),
            server_default=sa.text("'desktop'"),
            nullable=False,
        ),
        sa.Column(
            "interval_hours",
            sa.Integer(),
            server_default=sa.text("168"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("last_run_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_krs_location_active",
        "keyword_rank_schedules",
        ["location_id", "is_active"],
        unique=False,
    )

    op.create_table(
        "keyword_rank_results",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("keyword", sa.String(length=255), nullable=False),
        sa.Column("device", sa.String(length=20), nullable=False),
        sa.Column("map_pack_rank", sa.Integer(), nullable=True),
        sa.Column("organic_rank", sa.Integer(), nullable=True),
        sa.Column(
            "run_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_krr_location_kw_device_run",
        "keyword_rank_results",
        ["location_id", "keyword", "device", "run_at"],
        unique=False,
    )

    # ------------------------------------------------------------------ grants
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE "
        f"ON keyword_rank_schedules, keyword_rank_results TO {APP_ROLE};"
    )

    # ------------------------------------------------------------------ RLS
    # Both tables scope transitively through location_id (same pattern as
    # geogrid_scans): the locations subquery is RLS-filtered for the app role.

    op.execute("ALTER TABLE keyword_rank_schedules ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE keyword_rank_schedules FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON keyword_rank_schedules
            USING (location_id IN (SELECT id FROM locations))
            WITH CHECK (location_id IN (SELECT id FROM locations));
        """
    )

    op.execute("ALTER TABLE keyword_rank_results ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE keyword_rank_results FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON keyword_rank_results
            USING (location_id IN (SELECT id FROM locations))
            WITH CHECK (location_id IN (SELECT id FROM locations));
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON keyword_rank_results;")
    op.execute("ALTER TABLE keyword_rank_results NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE keyword_rank_results DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON keyword_rank_schedules;")
    op.execute("ALTER TABLE keyword_rank_schedules NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE keyword_rank_schedules DISABLE ROW LEVEL SECURITY;")

    op.drop_index("ix_krr_location_kw_device_run", table_name="keyword_rank_results")
    op.drop_table("keyword_rank_results")

    op.drop_index("ix_krs_location_active", table_name="keyword_rank_schedules")
    op.drop_table("keyword_rank_schedules")
