"""Structural guarantee: review gating is *impossible*, not merely blocked.

CLAUDE.md hard rule #1 and PRD §9.1.1: the product offers **no** mechanism to
route review requests by predicted sentiment or divert unhappy customers. This
test fails the build if anyone introduces a schema column or an API field that
could enable such routing — the "structurally absent" half of the guarantee — and
re-asserts the engine's runtime block as the belt-and-braces half.

It is intentionally a *guard* test: it should pass today (no such field exists)
and start failing the instant one is added, anywhere in the data model or API.
"""
import io
import tokenize
from pathlib import Path

import app.models  # noqa: F401 — registers every table on Base.metadata
from app.compliance import (
    ACTION_REVIEW_REQUEST,
    DEFAULT_RULESET,
    ExternalWrite,
    PolicyComplianceEngine,
)
from app.db.base import Base

# Field/column names that could only exist to gate reviews by sentiment or rating,
# or to divert negative feedback. Note: bare "sentiment" is allowed — reviews carry
# an AI-derived sentiment for *analysis* (schema §6); only routing/diversion fields
# are forbidden, so the tokens here are specific compounds.
FORBIDDEN_TOKENS = (
    "route_by_sentiment",
    "sentiment_route",
    "sentiment_routing",
    "sentiment_filter",
    "sentiment_threshold",
    "min_rating",
    "min_rating_to_request",
    "rating_threshold",
    "gate_by_rating",
    "rating_gate",
    "only_happy",
    "happy_only",
    "suppress_negative",
    "divert_negative",
    "negative_feedback_route",
    "private_feedback_route",
    "review_gate",
    "review_gating",
)

# Where columns and API fields live. app/compliance is deliberately excluded: it
# *names* these tokens precisely so it can block them.
_APP = Path(__file__).resolve().parents[2] / "app"
SCANNED_DIRS = ("models", "schemas", "api")


def test_no_mapped_column_enables_sentiment_routing():
    """No SQLAlchemy column on any table matches a gating token (schema column guard)."""
    offenders: list[str] = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            name = column.name.lower()
            if any(token in name for token in FORBIDDEN_TOKENS):
                offenders.append(f"{table.name}.{column.name}")
    assert not offenders, (
        "Sentiment-routing columns are forbidden (CLAUDE.md hard rule #1): "
        f"{offenders}"
    )


def _identifiers(source: str) -> set[str]:
    """All Python NAME tokens in ``source``, lower-cased.

    Tokenizing and keeping only NAMEs means comments and string literals are
    ignored — we flag actual column/field/parameter *identifiers*, not prose that
    happens to mention a rule key (the engine's own docs name these tokens to
    block them, which is legitimate).
    """
    names: set[str] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.NAME:
                names.add(tok.string.lower())
    except tokenize.TokenError:  # pragma: no cover - tolerate odd/partial files
        pass
    return names


def test_no_source_field_enables_sentiment_routing():
    """No field/column/param identifier in models, schemas, or API names a gating token."""
    offenders: list[str] = []
    for sub in SCANNED_DIRS:
        directory = _APP / sub
        if not directory.exists():
            continue
        for path in directory.rglob("*.py"):
            identifiers = _identifiers(path.read_text(encoding="utf-8"))
            for name in identifiers:
                for token in FORBIDDEN_TOKENS:
                    if token in name:
                        offenders.append(f"{path.relative_to(_APP)} -> {name}")
    assert not offenders, (
        "Sentiment-routing field detected in the data model / API surface "
        f"(gating must be structurally impossible): {offenders}"
    )


def test_only_equal_all_send_mode_is_permitted():
    """The campaign send mode is locked to equal_all — no gating mode exists."""
    assert DEFAULT_RULESET.allowed_send_modes == ("equal_all",)


def test_engine_blocks_any_sentiment_routed_request():
    """Belt-and-braces: even a runtime attempt to gate is blocked by the engine."""
    engine = PolicyComplianceEngine(DEFAULT_RULESET)
    for token in ("route_by_sentiment", "min_rating", "divert_negative"):
        decision = engine.evaluate(
            ExternalWrite(
                ACTION_REVIEW_REQUEST,
                content="Please leave us a review!",
                metadata={token: True},
            )
        )
        assert decision.blocked, f"gating field {token!r} was not blocked"
