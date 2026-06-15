"""usage_quotas_counters

Super-Admin hard monthly caps + consumption tracking (P1C-4, DB schema §3, PRD §5
FT-9):

* ``usage_quotas`` — per (scope, metric, period) hard cap with an ``on_exceed``
  mode (``pause`` / ``alert`` / ``block``).
* ``usage_counters`` — current-period consumption, incremented transactionally by
  workers. The unique constraint over (scope_type, scope_id, metric, period_start)
  is what makes the worker's atomic upsert-increment race-safe (schema §8).

The runtime ``lumen_app`` role gets full DML so workers can read caps and increment
counters. Like the entitlement override tables (revision ``c4e1a7b2f9d3``), these
are scope-keyed (``scope_id`` is a tenant_id *or* a client_id depending on
``scope_type``) and so are **not** covered by the P1A-2 tenant RLS policies; the
quota service always queries by explicit (scope_type, scope_id). Tenant-scoping
these tables at the DB layer is the same documented security follow-up noted there.

Revision ID: a1f7c4d92e58
Revises: e2c5f9a4b173
Create Date: 2026-06-15 11:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f7c4d92e58"
down_revision: Union[str, Sequence[str], None] = "e2c5f9a4b173"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "lumen_app"


def upgrade() -> None:
    op.create_table(
        "usage_quotas",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_id", sa.UUID(), nullable=False),
        sa.Column("metric", sa.String(length=40), nullable=False),
        sa.Column("period", sa.String(length=20), server_default=sa.text("'monthly'"), nullable=False),
        sa.Column("limit_value", sa.BigInteger(), nullable=False),
        sa.Column("on_exceed", sa.String(length=20), server_default=sa.text("'pause'"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scope_type", "scope_id", "metric", "period",
            name="uq_usage_quotas_scope_metric_period",
        ),
    )
    op.create_index("ix_usage_quotas_scope_id", "usage_quotas", ["scope_id"], unique=False)

    op.create_table(
        "usage_counters",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_id", sa.UUID(), nullable=False),
        sa.Column("metric", sa.String(length=40), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("used_value", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "updated_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scope_type", "scope_id", "metric", "period_start",
            name="uq_usage_counters_scope_metric_period",
        ),
    )
    op.create_index("ix_usage_counters_scope_id", "usage_counters", ["scope_id"], unique=False)
    op.create_index("ix_usage_counters_metric", "usage_counters", ["metric"], unique=False)
    op.create_index(
        "ix_usage_counters_period_start", "usage_counters", ["period_start"], unique=False
    )

    # Runtime app role reads caps and increments counters (mirrors P1A-2 grants).
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON usage_quotas, usage_counters "
        f"TO {APP_ROLE};"
    )


def downgrade() -> None:
    op.drop_index("ix_usage_counters_period_start", table_name="usage_counters")
    op.drop_index("ix_usage_counters_metric", table_name="usage_counters")
    op.drop_index("ix_usage_counters_scope_id", table_name="usage_counters")
    op.drop_table("usage_counters")
    op.drop_index("ix_usage_quotas_scope_id", table_name="usage_quotas")
    op.drop_table("usage_quotas")
