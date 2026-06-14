"""The Policy Compliance Engine — pure evaluation of one external write (P3A-2).

This is the heart of the "compliant by architecture" guarantee (PRD §9, CLAUDE.md
hard rules). Given a :class:`~app.compliance.actions.ExternalWrite` and a
:class:`~app.compliance.rulesets.Ruleset`, :meth:`PolicyComplianceEngine.evaluate`
returns a :class:`PolicyDecision`: ``passed`` or ``blocked`` plus the rule(s) that
fired and the ``ruleset_version`` that applied.

The engine is deliberately *pure* — no DB, no I/O, no HTTP — exactly like the
entitlement resolver (``app.entitlements.resolver``). That keeps every hard rule
unit-testable in isolation; the DB wiring and the ``422`` live one layer out in
``app.compliance.gateway``.

Rules enforced (each maps to a stable key in ``rulesets``):

* ``incentive_language``       — incentive words in prose (PRD §9.1.2).
* ``staff_name_solicitation``  — asking a reviewer to name a person (PRD §9.1.3).
* ``pressure_tactics``         — coercive / on-premise review pressure (PRD §9.3).
* ``review_gating``            — any sentiment-routing field in metadata, or a
  campaign send mode other than ``equal_all`` (PRD §9.1.1 / §9.1.6).
* ``review_mutation_attempt``  — an action that would create/edit/delete a review
  (reply-only — PRD §9.1.4).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from app.compliance.actions import ExternalWrite
from app.compliance.rulesets import (
    DEFAULT_RULESET,
    RULE_GATING,
    RULE_INCENTIVE,
    RULE_PRESSURE,
    RULE_REVIEW_MUTATION,
    RULE_STAFF_NAME,
    Ruleset,
)

OUTCOME_PASSED = "passed"
OUTCOME_BLOCKED = "blocked"


@dataclass(frozen=True)
class Violation:
    """One guardrail that fired, with the key written to ``compliance_events``."""

    rule: str
    message: str
    matched: str | None = None


@dataclass(frozen=True)
class PolicyDecision:
    """The engine's verdict on one action.

    ``violations`` is ordered by detection; :attr:`primary_rule` (the first) is the
    one surfaced in the ``422`` ``details.rule``, matching the single-rule shape of
    the API-spec §1 example. ``ruleset_version`` is always present so callers can
    record *which* Policy Center version applied, even on a pass.
    """

    outcome: str
    ruleset_version: int
    violations: tuple[Violation, ...] = ()

    @property
    def passed(self) -> bool:
        return self.outcome == OUTCOME_PASSED

    @property
    def blocked(self) -> bool:
        return self.outcome == OUTCOME_BLOCKED

    @property
    def primary_rule(self) -> str | None:
        return self.violations[0].rule if self.violations else None


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


def _word_present(term: str, haystack: str) -> bool:
    """True if ``term`` appears in ``haystack`` on alnum boundaries (case-insensitive).

    ``haystack`` is assumed lower-cased already. Boundaries are checked against
    ASCII word chars so ``discount`` matches in "10% discount!" but ``free`` does
    not match inside "freedom".
    """
    return _compile(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])").search(
        haystack
    ) is not None


class PolicyComplianceEngine:
    """Evaluate an :class:`ExternalWrite` against a :class:`Ruleset` (pure)."""

    def __init__(self, ruleset: Ruleset | None = None) -> None:
        self.ruleset = ruleset or DEFAULT_RULESET

    def evaluate(self, action: ExternalWrite) -> PolicyDecision:
        """Return a :class:`PolicyDecision` — all fired rules, in detection order."""
        rs = self.ruleset
        violations: list[Violation] = []

        # 1. Reply-only backstop: never create/edit/delete a review or rating.
        if action.action_type in rs.review_mutation_actions:
            violations.append(
                Violation(
                    RULE_REVIEW_MUTATION,
                    f"'{action.action_type}' is forbidden — the Reviews API is reply-only; "
                    "the platform cannot create, edit, or delete reviews or ratings.",
                    matched=action.action_type,
                )
            )

        # 2. Incentive language in the prose (PRD §9.1.2).
        if action.content:
            if term := self._incentive_hit(action.content):
                violations.append(
                    Violation(
                        RULE_INCENTIVE,
                        f"Incentive language is not allowed in review content: '{term}'.",
                        matched=term,
                    )
                )

            # 3. Staff-name solicitation (PRD §9.1.3).
            if pat := self._first_match(rs.staff_name_patterns, action.content):
                violations.append(
                    Violation(
                        RULE_STAFF_NAME,
                        "Soliciting reviews that name a specific staff member is not allowed.",
                        matched=pat,
                    )
                )

            # 4. Coercive / on-premise pressure (PRD §9.3).
            if pat := self._first_match(rs.pressure_patterns, action.content):
                violations.append(
                    Violation(
                        RULE_PRESSURE,
                        "Pressuring customers to leave a review is not allowed.",
                        matched=pat,
                    )
                )

        # 5. Review gating — the structural guarantee (PRD §9.1.1 / §9.1.6).
        if gating := self._gating_hit(action):
            violations.append(gating)

        outcome = OUTCOME_BLOCKED if violations else OUTCOME_PASSED
        return PolicyDecision(outcome, rs.version, tuple(violations))

    # --- rule helpers ----------------------------------------------------

    def _incentive_hit(self, content: str) -> str | None:
        """Return the first incentive term present, ignoring benign allow-phrases."""
        working = content.lower()
        for phrase in self.ruleset.incentive_allow_phrases:
            working = working.replace(phrase.lower(), " ")
        for term in self.ruleset.incentive_terms:
            if _word_present(term, working):
                return term
        return None

    @staticmethod
    def _first_match(patterns: tuple[str, ...], content: str) -> str | None:
        for pattern in patterns:
            if _compile(pattern).search(content):
                return pattern
        return None

    def _gating_hit(self, action: ExternalWrite) -> Violation | None:
        """Block any sentiment-routing field, or a non-equal send mode.

        Gating cannot be expressed through a sanctioned field (none exists — see
        ``test_no_sentiment_routing``); this catches any attempt to smuggle one in
        through an action's metadata at runtime.
        """
        meta = action.metadata or {}
        present = [f for f in self.ruleset.gating_fields if f in meta]
        if present:
            return Violation(
                RULE_GATING,
                "Review gating is prohibited: requests cannot be routed by predicted "
                f"sentiment (field: '{present[0]}').",
                matched=present[0],
            )
        send_mode = meta.get("send_mode")
        if send_mode is not None and send_mode not in self.ruleset.allowed_send_modes:
            return Violation(
                RULE_GATING,
                f"Review campaigns must send equally to all customers; "
                f"send_mode='{send_mode}' is not allowed.",
                matched="send_mode",
            )
        return None
