"""geogrid_and_locations

Adds the geo-grid rank-tracking tables (P2B-1):

* ``locations`` — physical outlets (DB schema §4): the geo-grid centroid and the
  unit protection operates on. Tenant-scoped by ``tenant_id``.
* ``geogrid_scans`` — one classic spatial-ranking scan per row (DB schema §5):
  per-node ``matrix_results`` + a rolled-up ``solv``. No ``tenant_id`` of its own;
  scoped transitively through ``location_id``.

Both tables get row-level security matching the P1A-2 pattern (revision
9029056a7245): ``locations`` keyed on its ``tenant_id``; ``geogrid_scans`` keyed on
membership in the (already RLS-filtered) ``locations`` set — the same transitive
trick used for ``user_roles``. The app role gets full DML; RLS constrains the rows.

Revision ID: 7f3c9d2e1a4b
Revises: c4e1a7b2f9d3
Create Date: 2026-06-14 14:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7f3c9d2e1a4b"
down_revision: Union[str, Sequence[str], None] = "c4e1a7b2f9d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "lumen_app"

# Same fail-closed tenant expression as the P1A-2 RLS migration: a context-less
# query collapses '' -> NULL and matches no rows rather than erroring.
TENANT_EXPR = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"


def upgrade() -> None:
    # --- tables -----------------------------------------------------------
    op.create_table(
        "locations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("google_place_id", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column(
            "profile_data_live",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("profile_data_locked", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_protected", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "revert_mode", sa.String(length=20), server_default=sa.text("'alert_only'"), nullable=False
        ),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_locations_tenant_id", "locations", ["tenant_id"], unique=False)
    op.create_index("ix_locations_client_id", "locations", ["client_id"], unique=False)
    op.create_index("ix_locations_google_place_id", "locations", ["google_place_id"], unique=False)

    op.create_table(
        "geogrid_scans",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("search_term", sa.String(length=255), nullable=False),
        sa.Column("grid_dimensions", sa.Integer(), nullable=False),
        sa.Column("matrix_results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("solv", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("run_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_geogrid_scans_location_run_at", "geogrid_scans", ["location_id", "run_at"], unique=False
    )

    # --- grants -----------------------------------------------------------
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON locations, geogrid_scans TO {APP_ROLE};"
    )

    # --- RLS: locations (direct tenant_id) --------------------------------
    op.execute("ALTER TABLE locations ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE locations FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON locations
            USING (tenant_id = {TENANT_EXPR})
            WITH CHECK (tenant_id = {TENANT_EXPR});
        """
    )

    # --- RLS: geogrid_scans (transitive via locations) --------------------
    # The subquery is itself RLS-filtered for the app role, so this resolves to
    # exactly the current tenant's locations' scans (cf. user_roles in P1A-2).
    op.execute("ALTER TABLE geogrid_scans ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE geogrid_scans FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON geogrid_scans
            USING (location_id IN (SELECT id FROM locations))
            WITH CHECK (location_id IN (SELECT id FROM locations));
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON geogrid_scans;")
    op.execute("ALTER TABLE geogrid_scans NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE geogrid_scans DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON locations;")
    op.execute("ALTER TABLE locations NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE locations DISABLE ROW LEVEL SECURITY;")

    op.drop_index("ix_geogrid_scans_location_run_at", table_name="geogrid_scans")
    op.drop_table("geogrid_scans")
    op.drop_index("ix_locations_google_place_id", table_name="locations")
    op.drop_index("ix_locations_client_id", table_name="locations")
    op.drop_index("ix_locations_tenant_id", table_name="locations")
    op.drop_table("locations")
