"""sso_tenant_config

Adds ``sso_config`` JSONB to ``tenants`` for SAML/OIDC provider settings
(P1B-3 scaffold — issuer URL, certificate, attribute mapping, etc.).

Revision ID: f3a9c1e8b042
Revises: d5a8c3e6b210
Create Date: 2026-06-15 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3a9c1e8b042"
down_revision: Union[str, Sequence[str], None] = "d5a8c3e6b210"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "lumen_app"


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "sso_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "sso_config")
