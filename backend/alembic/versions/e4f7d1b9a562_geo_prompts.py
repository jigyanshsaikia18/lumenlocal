"""geo_prompts

Adds the niche-aware prompt library table (P2C-4):

* ``geo_prompts`` — prompt templates for AI-search visibility scans. Stores both
  default global prompts (is_custom=false, tenant_id=NULL) and custom agency-owned
  prompts (is_custom=true, tenant_id set). GEO scans sample from both pools
  filtered by niche and tenant.

RLS allows: default prompts (is_custom=false) visible to all + custom prompts
(is_custom=true) visible only to their owning tenant.

Revision ID: e4f7d1b9a562
Revises: d1b6f8a3c204
Create Date: 2026-06-16 10:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e4f7d1b9a562"
down_revision: Union[str, Sequence[str], None] = "d1b6f8a3c204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "lumen_app"


def upgrade() -> None:
    op.create_table(
        "geo_prompts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("niche", sa.String(length=120), nullable=True),
        sa.Column("prompt", sa.String(length=500), nullable=False),
        sa.Column("is_custom", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_geo_prompts_niche", "geo_prompts", ["niche"], unique=False)
    op.create_index(
        "ix_geo_prompts_custom_tenant", "geo_prompts", ["is_custom", "tenant_id"], unique=False
    )

    # --- grants -----------------------------------------------------------
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON geo_prompts TO {APP_ROLE};")

    # --- RLS: default + custom scoped by tenant ----------------------------
    op.execute("ALTER TABLE geo_prompts ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE geo_prompts FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON geo_prompts
            USING (
                NOT is_custom
                OR tenant_id = current_setting('app.tenant_id')::UUID
            )
            WITH CHECK (
                NOT is_custom
                OR tenant_id = current_setting('app.tenant_id')::UUID
            );
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON geo_prompts;")
    op.execute("ALTER TABLE geo_prompts NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE geo_prompts DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_geo_prompts_custom_tenant", table_name="geo_prompts")
    op.drop_index("ix_geo_prompts_niche", table_name="geo_prompts")
    op.drop_table("geo_prompts")
