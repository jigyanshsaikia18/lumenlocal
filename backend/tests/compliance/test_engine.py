"""The Policy Compliance Engine's hard rules (P3A-2), proven on the built-in v1
ruleset. Pure — no DB — like the entitlement-resolver suite.

Anchors the three guarantees the ticket calls out by name: an incentive word in a
review reply is blocked, a staff-name solicitation is blocked, and review gating
is impossible (the structural-absence half lives in test_no_sentiment_routing).
"""
import pytest

from app.compliance import (
    ACTION_REVIEW_REPLY,
    ACTION_REVIEW_REQUEST,
    DEFAULT_RULESET,
    ExternalWrite,
    PolicyComplianceEngine,
    RULE_GATING,
    RULE_INCENTIVE,
    RULE_REVIEW_MUTATION,
    RULE_STAFF_NAME,
)


@pytest.fixture
def engine() -> PolicyComplianceEngine:
    return PolicyComplianceEngine(DEFAULT_RULESET)


# --- incentive language (PRD §9.1.2) ------------------------------------


def test_incentive_word_discount_in_reply_is_blocked(engine):
    decision = engine.evaluate(
        ExternalWrite(
            ACTION_REVIEW_REPLY,
            content="Thanks so much! Show this reply for a 10% discount next time.",
        )
    )
    assert decision.blocked
    assert decision.primary_rule == RULE_INCENTIVE
    # The block carries the rule + the ruleset version (the 422 details, API §1).
    assert decision.ruleset_version == DEFAULT_RULESET.version
    assert any(v.matched == "discount" for v in decision.violations)


@pytest.mark.parametrize("word", ["free", "coupon", "gift card", "raffle", "loyalty points"])
def test_other_incentive_terms_blocked(engine, word):
    decision = engine.evaluate(
        ExternalWrite(ACTION_REVIEW_REQUEST, content=f"Leave a review and get a {word}!")
    )
    assert decision.blocked
    assert decision.primary_rule == RULE_INCENTIVE


def test_benign_feel_free_is_not_an_incentive(engine):
    # "feel free" embeds "free" but is not incentive language — must pass.
    decision = engine.evaluate(
        ExternalWrite(ACTION_REVIEW_REPLY, content="Thank you! Feel free to visit again soon.")
    )
    assert decision.passed
    assert decision.violations == ()


def test_discount_substring_does_not_false_positive(engine):
    # Word-boundary matching: "discounted" should not trip on "discount"? It is
    # still an incentive context; but "freedom" must not match "free".
    decision = engine.evaluate(
        ExternalWrite(ACTION_REVIEW_REPLY, content="We value your freedom to choose us.")
    )
    assert decision.passed


# --- staff-name solicitation (PRD §9.1.3) -------------------------------


def test_staff_name_solicitation_is_blocked(engine):
    decision = engine.evaluate(
        ExternalWrite(
            ACTION_REVIEW_REQUEST,
            content="We'd love a review — please mention our manager Sarah by name!",
        )
    )
    assert decision.blocked
    assert RULE_STAFF_NAME in {v.rule for v in decision.violations}


def test_staff_role_solicitation_is_blocked(engine):
    decision = engine.evaluate(
        ExternalWrite(
            ACTION_REVIEW_REQUEST,
            content="When you review us, name the technician who helped you.",
        )
    )
    assert decision.blocked
    assert RULE_STAFF_NAME in {v.rule for v in decision.violations}


def test_clean_reply_passes(engine):
    decision = engine.evaluate(
        ExternalWrite(
            ACTION_REVIEW_REPLY,
            content="Thank you for the kind words — we're glad you enjoyed your visit!",
        )
    )
    assert decision.passed


# --- review gating: structurally impossible (PRD §9.1.1 / §9.1.6) -------


def test_gating_field_in_metadata_is_blocked(engine):
    # Even if some module tried to smuggle a sentiment-routing field at runtime,
    # the engine blocks on its mere presence.
    decision = engine.evaluate(
        ExternalWrite(
            ACTION_REVIEW_REQUEST,
            content="Please leave us a review!",
            metadata={"route_by_sentiment": True},
        )
    )
    assert decision.blocked
    assert decision.primary_rule == RULE_GATING


def test_non_equal_send_mode_is_blocked(engine):
    decision = engine.evaluate(
        ExternalWrite(
            ACTION_REVIEW_REQUEST,
            content="Please leave us a review!",
            metadata={"send_mode": "happy_only"},
        )
    )
    assert decision.blocked
    assert decision.primary_rule == RULE_GATING


def test_equal_all_send_mode_passes(engine):
    decision = engine.evaluate(
        ExternalWrite(
            ACTION_REVIEW_REQUEST,
            content="Please leave us a review!",
            metadata={"send_mode": "equal_all"},
        )
    )
    assert decision.passed


# --- reply-only backstop (PRD §9.1.4) -----------------------------------


def test_review_mutation_action_is_blocked(engine):
    # No endpoint emits these, but the engine refuses them as defence-in-depth.
    decision = engine.evaluate(ExternalWrite("review_delete", content=""))
    assert decision.blocked
    assert decision.primary_rule == RULE_REVIEW_MUTATION
