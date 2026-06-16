"""Seed geo_prompts with default templates (P2C-4)

Populates the geo_prompts table with a starter set of niche-aware prompt templates.
These are the default, global prompts (is_custom=false, tenant_id=NULL) that all
tenants can use out-of-the-box.

Revision ID: f5g8e2h0c314
Revises: e4f7d1b9a562
Create Date: 2026-06-16 10:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f5g8e2h0c314"
down_revision: Union[str, Sequence[str], None] = "e4f7d1b9a562"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Default prompt templates: global (niche=NULL) and niche-specific
    default_prompts = [
        # Global prompts
        ("best {category} near me", None),
        ("{category} open now in {area}", None),
        ("where to find {category} nearby", None),
        ("top-rated {category}", None),
        # Plumber
        ("best plumber near me", "plumber"),
        ("emergency plumbing services {area}", "plumber"),
        ("24/7 plumber {city}", "plumber"),
        # Restaurant
        ("best restaurant near me", "restaurant"),
        ("where to eat {area}", "restaurant"),
        ("{cuisine} restaurant {city}", "restaurant"),
        # Dentist
        ("best dentist near me", "dentist"),
        ("dental clinic open today {area}", "dentist"),
        ("cosmetic dentist {city}", "dentist"),
        # HVAC
        ("ac repair {area}", "hvac"),
        ("emergency heating {city}", "hvac"),
        ("best hvac company near me", "hvac"),
        # Hair/Salon
        ("best salon near me", "salon"),
        ("haircut {city} open now", "salon"),
        ("{hair_type} specialist {area}", "salon"),
    ]

    bind = op.get_bind()
    stmt = sa.text(
        """
        INSERT INTO geo_prompts (niche, prompt, is_custom, tenant_id)
        VALUES (:niche, :prompt, false, NULL)
        """
    )
    for prompt_text, niche in default_prompts:
        bind.execute(stmt, {"niche": niche, "prompt": prompt_text})


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM geo_prompts WHERE is_custom = false AND tenant_id IS NULL")
    )
