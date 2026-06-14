"""profile_protection

Adds the profile-protection trail (P4A, DB schema §7):

* ``profile_change_events`` — one row per detected change to a monitored profile
  field, with ``severity`` and the ``action_taken`` by the bounded-revert policy
  (``alerted`` / ``reverted`` / ``ignored`` — ``app.protection.revert``). It is the
  proof that a critical change was caught and handled (PRD §7). No ``tenant_id`` of
  its own; scoped transitively through ``location_id``.

The table is **append-only**: the app role gets SELECT + INSERT only (no UPDATE /
DELETE), like ``compliance_events`` — the trail must not be rewritten. RLS matches
the ``geogrid_scans`` transitive pattern (revision 7f3c9d2e1a4b): rows are visible
only when their ``location_id`` is in the (already RLS-filtered) ``locations`` set,
so a tenant sees exactly its own locations' change events.

Revision ID: d5a8c3e6b210
Revises: b7d4e2f10a93
Create Date: 2026-06-14 16:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d5a8c3e6b210"
down_revision: Union[str, Sequence[str], None] = "b7d4e2f10a93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "lumen_app"


def upgrade() -> None:
    op.create_table(
        "profile_change_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("field", sa.String(length=60), nullable=True),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("action_taken", sa.String(length=20), nullable=True),
        sa.Column(
            "detected_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_profile_change_events_location_detected_at",
        "profile_change_events",
        ["location_id", "detected_at"],
        unique=False,
    )

    # Append-only trail: SELECT to read it back, INSERT to append — never edited.
    op.execute(f"GRANT SELECT, INSERT ON profile_change_events TO {APP_ROLE};")

    # RLS: transitive via locations (the subquery is itself RLS-filtered for the app
    # role, so it resolves to exactly the current tenant's locations' events).
    op.execute("ALTER TABLE profile_change_events ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE profile_change_events FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON profile_change_events
            USING (location_id IN (SELECT id FROM locations))
            WITH CHECK (location_id IN (SELECT id FROM locations));
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON profile_change_events;")
    op.execute("ALTER TABLE profile_change_events NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE profile_change_events DISABLE ROW LEVEL SECURITY;")
    op.drop_index(
        "ix_profile_change_events_location_detected_at", table_name="profile_change_events"
    )
    op.drop_table("profile_change_events")
