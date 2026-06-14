"""Versioned, machine-evaluable guardrails — the Policy Center ruleset (schema §7).

A :class:`Ruleset` is the data the :class:`~app.compliance.engine.PolicyComplianceEngine`
interprets. It is the in-code mirror of one ``policy_rulesets`` row: ``version`` is
the integer that propagates platform-wide and is echoed back in every ``422`` and
``compliance_events.ruleset_version`` (API spec §1, PRD §9.2), and the rest is the
``rules`` JSONB.

Keeping the guardrails as *data* (not hard-coded ``if`` branches) is the whole
point of the Policy Center: when Google or the FTC change the rules, a Super Admin
publishes a new ruleset version and every tenant tightens at once — no deploy
(PRD §9.2). :meth:`to_rules` / :meth:`from_rules` round-trip the data to the JSONB
column so the DB row and this object stay one representation.

The rule *keys* below are the stable strings written to
``compliance_events.rule_violated`` and returned in the ``422`` ``details.rule``.
They are part of the API contract — do not rename them lightly.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# --- Stable rule keys (contract: surfaced in 422 details + compliance_events) ---
RULE_INCENTIVE = "incentive_language"
RULE_GATING = "review_gating"
RULE_STAFF_NAME = "staff_name_solicitation"
RULE_PRESSURE = "pressure_tactics"
RULE_REVIEW_MUTATION = "review_mutation_attempt"


@dataclass(frozen=True)
class Ruleset:
    """One versioned set of guardrails (the in-code form of a ``policy_rulesets`` row).

    Fields:
        version: Monotonic Policy Center version; echoed in every block/event.
        incentive_terms: Words/phrases that make a review request/reply an
            *incentivized* one — blocked outright (PRD §9.1.2).
        incentive_allow_phrases: Benign phrases that contain an incentive term as
            a substring ("feel free") and must NOT trip the linter.
        gating_fields: Structured field names that could only exist to route
            requests by predicted sentiment. Their mere presence is a block — this
            is how "gating is structurally impossible" is *enforced* (PRD §9.1.1).
        allowed_send_modes: The only campaign send modes permitted (``equal_all``).
        staff_name_patterns: Regexes detecting solicitation of reviews that name a
            specific staff member (PRD §9.1.3).
        pressure_patterns: Regexes detecting on-premise / coercive review pressure.
        review_mutation_actions: Action types that would create/edit/delete a
            review — always blocked (reply-only; PRD §9.1.4).
    """

    version: int
    incentive_terms: tuple[str, ...]
    incentive_allow_phrases: tuple[str, ...]
    gating_fields: tuple[str, ...]
    allowed_send_modes: tuple[str, ...]
    staff_name_patterns: tuple[str, ...]
    pressure_patterns: tuple[str, ...]
    review_mutation_actions: tuple[str, ...]

    def to_rules(self) -> dict[str, Any]:
        """Serialise the guardrails to the ``policy_rulesets.rules`` JSONB shape."""
        return {
            "incentive_terms": list(self.incentive_terms),
            "incentive_allow_phrases": list(self.incentive_allow_phrases),
            "gating_fields": list(self.gating_fields),
            "allowed_send_modes": list(self.allowed_send_modes),
            "staff_name_patterns": list(self.staff_name_patterns),
            "pressure_patterns": list(self.pressure_patterns),
            "review_mutation_actions": list(self.review_mutation_actions),
        }

    @classmethod
    def from_rules(cls, version: int, rules: Mapping[str, Any]) -> "Ruleset":
        """Rebuild a ``Ruleset`` from a DB row (``version`` + ``rules`` JSONB).

        Missing keys fall back to the :data:`DEFAULT_RULESET` value so a partial
        or older ruleset row still produces a complete, safe object.
        """

        def _tuple(key: str) -> tuple[str, ...]:
            raw: Sequence[str] | None = rules.get(key)
            if raw is None:
                return getattr(DEFAULT_RULESET, key)
            return tuple(raw)

        return cls(
            version=version,
            incentive_terms=_tuple("incentive_terms"),
            incentive_allow_phrases=_tuple("incentive_allow_phrases"),
            gating_fields=_tuple("gating_fields"),
            allowed_send_modes=_tuple("allowed_send_modes"),
            staff_name_patterns=_tuple("staff_name_patterns"),
            pressure_patterns=_tuple("pressure_patterns"),
            review_mutation_actions=_tuple("review_mutation_actions"),
        )


# The built-in v1 guardrails. This is the offline fallback used when no DB row is
# loaded (e.g. the pure unit suite) and is mirrored, value-for-value, by the seed
# in the policy_compliance migration. PRD §9.1 is the source for every entry.
DEFAULT_RULESET = Ruleset(
    version=1,
    # Incentive language (PRD §9.1.2). Matched on word boundaries, case-insensitive.
    incentive_terms=(
        "free",
        "discount",
        "coupon",
        "gift",
        "gift card",
        "raffle",
        "giveaway",
        "voucher",
        "cashback",
        "cash back",
        "prize",
        "reward",
        "rewards",
        "loyalty points",
        "store credit",
    ),
    # Common benign phrases that embed an incentive term — never a violation.
    incentive_allow_phrases=(
        "feel free",
        "free to",
        "free time",
        "free of charge",
        "toll free",
        "toll-free",
        "gift of your time",
    ),
    # Sentiment-routing fields. If any appears in an action's metadata it can only
    # be an attempt to gate — block on presence. Keep this list broad; it is the
    # runtime half of "gating is structurally impossible" (the other half is that
    # no such column/field exists — asserted by test_no_sentiment_routing).
    gating_fields=(
        "route_by_sentiment",
        "sentiment_route",
        "sentiment_routing",
        "sentiment_filter",
        "sentiment_threshold",
        "min_rating",
        "min_rating_to_request",
        "rating_threshold",
        "gate_by_rating",
        "only_happy",
        "happy_only",
        "suppress_negative",
        "divert_negative",
        "negative_feedback_route",
        "private_feedback_route",
    ),
    allowed_send_modes=("equal_all",),
    # Staff-name solicitation (PRD §9.1.3): asking a reviewer to name a person.
    staff_name_patterns=(
        r"\bmention\b[^.?!]{0,60}\bby name\b",
        r"\bask(?:ing|ed)?\s+for\b[^.?!]{0,40}\bby name\b",
        r"\bmention\b[^.?!]{0,40}\b(?:our|my|the|your)\b[^.?!]{0,40}\bname\b",
        r"\b(?:leave|write|give|post)\b[^.?!]{0,80}\breview\b[^.?!]{0,80}\bby name\b",
        r"\b(?:name|mention)\b[^.?!]{0,30}\b(?:server|waiter|waitress|technician|stylist|agent|rep|associate|employee|staff member)\b",
    ),
    # On-premise / coercive review pressure (PRD §9.1.3, §9.3).
    pressure_patterns=(
        r"\byou\s+(?:must|have to|need to|are required to)\b[^.?!]{0,40}\breview\b",
        r"\b(?:before|until)\b[^.?!]{0,40}\bleave\b[^.?!]{0,20}\breview\b",
        r"\breview\b[^.?!]{0,20}\bbefore you (?:leave|go)\b",
    ),
    review_mutation_actions=(
        "review_create",
        "review_edit",
        "review_update",
        "review_delete",
        "rating_edit",
        "rating_update",
    ),
)
