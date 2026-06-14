"""Policy Center + compliance-event tables (DB schema §7).

``PolicyRuleset`` is one versioned set of guardrails (the "protect against
frequent Google/FTC updates" mechanism, PRD §9.2). Exactly one row is active at a
time; publishing a new version propagates platform-wide. It is global reference
data — no ``tenant_id`` — so the runtime app role gets read-only access.

``ComplianceEvent`` is the append-only proof trail of every blocked/flagged write
(PRD §9, the audit that sells the compliance value). It is tenant-scoped, so the
gateway writes one per block with the rule and the ruleset version that applied.

The in-code mirror of ``PolicyRuleset.rules`` is ``app.compliance.rulesets.Ruleset``
(``to_rules`` / ``from_rules`` round-trip between them).
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Integer, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PolicyRuleset(Base):
    """A versioned Policy Center ruleset (schema §7)."""

    __tablename__ = "policy_rulesets"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    # Increments on each Google/FTC update; echoed in every 422 + compliance_event.
    version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # Machine-evaluable guardrails — the JSONB form of compliance.rulesets.Ruleset.
    rules: Mapped[dict] = mapped_column(JSONB, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), server_default=text("CURRENT_TIMESTAMP")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )


class ComplianceEvent(Base):
    """A blocked/flagged outbound write — the append-only compliance trail (schema §7)."""

    __tablename__ = "compliance_events"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # review_reply / review_request / post / listing_edit (compliance.actions).
    action_type: Mapped[str] = mapped_column(String(30), nullable=True)
    # blocked / flagged / passed.
    outcome: Mapped[str] = mapped_column(String(20), nullable=True)
    # The rule key that fired, e.g. incentive_language / review_gating / staff_name_solicitation.
    rule_violated: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Which Policy Center version applied.
    ruleset_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), server_default=text("CURRENT_TIMESTAMP"), index=True
    )
