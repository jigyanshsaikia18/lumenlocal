"""Policy Compliance Engine (P3A-2) — the mandatory gateway for external writes.

Compliant-by-architecture (PRD §9, CLAUDE.md): every outbound write to Google is
described as an :class:`ExternalWrite`, evaluated by the pure
:class:`PolicyComplianceEngine` against a versioned :class:`Ruleset`, and pushed
through :class:`PolicyGateway` — the single sanctioned path, which blocks hard
violations with ``422 {rule, ruleset_version}`` and logs them to
``compliance_events``. Nothing reaches Google un-checked.
"""
from app.compliance.actions import (
    ACTION_LISTING_EDIT,
    ACTION_POST,
    ACTION_REVIEW_REPLY,
    ACTION_REVIEW_REQUEST,
    ExternalWrite,
)
from app.compliance.engine import (
    PolicyComplianceEngine,
    PolicyDecision,
    Violation,
)
from app.compliance.gateway import (
    ComplianceEventData,
    ComplianceEventSink,
    PolicyGateway,
    SqlAlchemyComplianceEventSink,
    build_gateway,
    load_active_ruleset,
)
from app.compliance.rulesets import (
    DEFAULT_RULESET,
    RULE_GATING,
    RULE_INCENTIVE,
    RULE_PRESSURE,
    RULE_REVIEW_MUTATION,
    RULE_STAFF_NAME,
    Ruleset,
)

__all__ = [
    "ACTION_LISTING_EDIT",
    "ACTION_POST",
    "ACTION_REVIEW_REPLY",
    "ACTION_REVIEW_REQUEST",
    "ComplianceEventData",
    "ComplianceEventSink",
    "DEFAULT_RULESET",
    "ExternalWrite",
    "PolicyComplianceEngine",
    "PolicyDecision",
    "PolicyGateway",
    "RULE_GATING",
    "RULE_INCENTIVE",
    "RULE_PRESSURE",
    "RULE_REVIEW_MUTATION",
    "RULE_STAFF_NAME",
    "Ruleset",
    "SqlAlchemyComplianceEventSink",
    "Violation",
    "build_gateway",
    "load_active_ruleset",
]
