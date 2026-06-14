"""policy_compliance

Policy Compliance Engine tables (P3A, DB schema §7):

* ``policy_rulesets`` — the Policy Center: versioned, machine-evaluable guardrails
  (PRD §9.2). Global reference data (no ``tenant_id``); the runtime app role gets
  read-only access, like ``plans``. Seeds the built-in **v1** ruleset so the
  gateway is functional on a fresh DB; this JSON mirrors
  ``app.compliance.rulesets.DEFAULT_RULESET`` value-for-value.
* ``compliance_events`` — the append-only proof trail of blocked/flagged outbound
  writes (the audit that sells the compliance value). Tenant-scoped, so it gets
  row-level security on ``tenant_id`` matching the P1A-2 pattern (revision
  9029056a7245); the app role gets SELECT + INSERT only (events are not edited).

Revision ID: b7d4e2f10a93
Revises: 7f3c9d2e1a4b
Create Date: 2026-06-14 15:10:00.000000
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7d4e2f10a93"
down_revision: Union[str, Sequence[str], None] = "7f3c9d2e1a4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "lumen_app"

# Same fail-closed tenant expression as the P1A-2 RLS migration.
TENANT_EXPR = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"

# Built-in v1 guardrails — mirrors app.compliance.rulesets.DEFAULT_RULESET.to_rules().
# Kept as a static literal here so the migration is reproducible (not coupled to
# importable app code); the two are kept in sync and a test asserts it.
DEFAULT_RULES = {
    "incentive_terms": [
        "free", "discount", "coupon", "gift", "gift card", "raffle", "giveaway",
        "voucher", "cashback", "cash back", "prize", "reward", "rewards",
        "loyalty points", "store credit",
    ],
    "incentive_allow_phrases": [
        "feel free", "free to", "free time", "free of charge", "toll free",
        "toll-free", "gift of your time",
    ],
    "gating_fields": [
        "route_by_sentiment", "sentiment_route", "sentiment_routing",
        "sentiment_filter", "sentiment_threshold", "min_rating",
        "min_rating_to_request", "rating_threshold", "gate_by_rating",
        "only_happy", "happy_only", "suppress_negative", "divert_negative",
        "negative_feedback_route", "private_feedback_route",
    ],
    "allowed_send_modes": ["equal_all"],
    "staff_name_patterns": [
        r"\bmention\b[^.?!]{0,60}\bby name\b",
        r"\bask(?:ing|ed)?\s+for\b[^.?!]{0,40}\bby name\b",
        r"\bmention\b[^.?!]{0,40}\b(?:our|my|the|your)\b[^.?!]{0,40}\bname\b",
        r"\b(?:leave|write|give|post)\b[^.?!]{0,80}\breview\b[^.?!]{0,80}\bby name\b",
        r"\b(?:name|mention)\b[^.?!]{0,30}\b(?:server|waiter|waitress|technician|stylist|agent|rep|associate|employee|staff member)\b",
    ],
    "pressure_patterns": [
        r"\byou\s+(?:must|have to|need to|are required to)\b[^.?!]{0,40}\breview\b",
        r"\b(?:before|until)\b[^.?!]{0,40}\bleave\b[^.?!]{0,20}\breview\b",
        r"\breview\b[^.?!]{0,20}\bbefore you (?:leave|go)\b",
    ],
    "review_mutation_actions": [
        "review_create", "review_edit", "review_update", "review_delete",
        "rating_edit", "rating_update",
    ],
}


def upgrade() -> None:
    # --- policy_rulesets (global reference data) --------------------------
    op.create_table(
        "policy_rulesets",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "effective_from", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policy_rulesets_version", "policy_rulesets", ["version"], unique=False)

    # --- compliance_events (tenant-scoped audit trail) -------------------
    op.create_table(
        "compliance_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(length=30), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=True),
        sa.Column("rule_violated", sa.String(length=120), nullable=True),
        sa.Column("ruleset_version", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compliance_events_tenant_id", "compliance_events", ["tenant_id"], unique=False)
    op.create_index("ix_compliance_events_created_at", "compliance_events", ["created_at"], unique=False)

    # --- grants ----------------------------------------------------------
    # Policy Center is read-only at runtime (published via the admin/migration path).
    op.execute(f"GRANT SELECT ON policy_rulesets TO {APP_ROLE};")
    # Events are appended by the gateway and read back as the proof trail — never edited.
    op.execute(f"GRANT SELECT, INSERT ON compliance_events TO {APP_ROLE};")

    # --- RLS: compliance_events (direct tenant_id) -----------------------
    op.execute("ALTER TABLE compliance_events ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE compliance_events FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON compliance_events
            USING (tenant_id = {TENANT_EXPR})
            WITH CHECK (tenant_id = {TENANT_EXPR});
        """
    )

    # --- seed the built-in v1 ruleset (active) ---------------------------
    op.execute(
        sa.text(
            "INSERT INTO policy_rulesets (version, rules, is_active) "
            "VALUES (1, CAST(:rules AS jsonb), true)"
        ).bindparams(rules=json.dumps(DEFAULT_RULES))
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON compliance_events;")
    op.execute("ALTER TABLE compliance_events NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE compliance_events DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_compliance_events_created_at", table_name="compliance_events")
    op.drop_index("ix_compliance_events_tenant_id", table_name="compliance_events")
    op.drop_table("compliance_events")
    op.drop_index("ix_policy_rulesets_version", table_name="policy_rulesets")
    op.drop_table("policy_rulesets")
