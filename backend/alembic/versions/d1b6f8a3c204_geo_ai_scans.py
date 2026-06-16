"""geo_ai_scans

Adds the AI-search visibility table (P2C-2, the GEO flagship):

* ``geo_ai_scans`` — one geo-grid-for-AI scan per row (DB schema §5): per-node
  ``matrix_results`` (mention/prominence per sample run), the rolled-up ``saiv``,
  and the ``cited_sources`` the AI referenced. No ``tenant_id`` of its own; scoped
  transitively through ``location_id``, exactly like ``geogrid_scans``.

RLS matches the ``geogrid_scans`` pattern (revision 7f3c9d2e1a4b): membership in
the (already RLS-filtered) ``locations`` set, so a query resolves to exactly the
current tenant's locations' scans. The app role gets full DML; RLS constrains the
rows.

Revision ID: d1b6f8a3c204
Revises: c9f2a7e4b831
Create Date: 2026-06-16 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d1b6f8a3c204"
down_revision: Union[str, Sequence[str], None] = "c9f2a7e4b831"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "lumen_app"


def upgrade() -> None:
    op.create_table(
        "geo_ai_scans",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("prompt", sa.String(length=500), nullable=False),
        sa.Column("grid_dimensions", sa.Integer(), nullable=True),
        sa.Column("sample_runs", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("matrix_results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("saiv", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "cited_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("run_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_geo_ai_scans_location_run_at", "geo_ai_scans", ["location_id", "run_at"], unique=False
    )

    # --- grants -----------------------------------------------------------
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON geo_ai_scans TO {APP_ROLE};")

    # --- RLS: transitive via locations ------------------------------------
    op.execute("ALTER TABLE geo_ai_scans ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE geo_ai_scans FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON geo_ai_scans
            USING (location_id IN (SELECT id FROM locations))
            WITH CHECK (location_id IN (SELECT id FROM locations));
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON geo_ai_scans;")
    op.execute("ALTER TABLE geo_ai_scans NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE geo_ai_scans DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_geo_ai_scans_location_run_at", table_name="geo_ai_scans")
    op.drop_table("geo_ai_scans")
