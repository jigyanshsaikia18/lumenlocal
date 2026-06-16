"""AI-readiness audit + GEO recommendation engine (PRD Module 3, GEO-7..GEO-9).

This is the *optimization* half of the GEO flagship: where the scan worker
(P2C-2) measures how visible a business already is across AI surfaces, the audit
here scores the **profile signals that feed those AI answers** and turns the gaps
into a prioritized, profile-specific action list.

GEO-7 enumerates the signals AI systems lean on when answering about a local
business, and each becomes one entry in :data:`SIGNALS`:

* **category specificity** — a precise primary category (plus secondaries) is the
  strongest hint AI uses to decide which queries you match.
* **products/services completeness** — the catalog AI pulls from for "best X" /
  "who does Y" prompts.
* **NAP consistency** — mismatched name/address/phone across directories reads to
  an AI as a verification failure (GEO-8, the entity-consistency checker).
* **review recency / sentiment / coverage** — fresh, positive, plentiful reviews.
* **photo recency / descriptive naming** — a Vision-AI signal of an active, real
  business.
* **Q&A coverage** — answered questions feed conversational answers directly.
* **post freshness** — recent posts signal a current, operating business.
* **attributes** — structured facts (amenities, service options) AI can cite.

Everything here is a **pure function of a profile dict** (the location's
``profile_data_live`` JSONB) and a reference ``now`` — no I/O, no DB, no clock
side-effects — so the whole engine is unit-testable in isolation and the same
inputs always yield the same prioritized actions.

Scoring model: each signal scores ``0..100`` and carries a fixed weight; the
weights sum to 100 so the weighted mean is itself a ``0..100`` overall score.
A recommendation is emitted for every signal with a gap (``score < 100``); its
**impact** is the number of overall points recoverable by closing that gap
(``weight * (100 - score) / 100``), and recommendations sort by impact so the
agency always sees the highest-leverage fix first (GEO-9).

Compliance note (CLAUDE.md): the review recommendation only ever proposes an
**equal-send** request campaign. There is deliberately no "ask happy customers"
branch — review gating is structurally absent from the product.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone

# --------------------------------------------------------------------------- #
# Result types                                                                  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SignalScore:
    """One scored GEO signal: its 0–100 grade, weight, and supporting detail."""

    key: str
    label: str
    weight: float
    score: float
    detail: dict
    action: str | None


@dataclass(frozen=True)
class Recommendation:
    """A single prioritized, profile-specific action (GEO-9)."""

    signal: str
    action: str
    priority: str  # "high" | "medium" | "low"
    impact_points: float  # overall-score points recoverable by closing the gap


@dataclass(frozen=True)
class AiReadinessReport:
    """The full audit: overall grade, per-signal breakdown, ranked actions."""

    overall_score: float
    signals: list[SignalScore] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #

_GENERIC_PHOTO_PREFIXES = ("img", "image", "photo", "dsc", "screenshot", "untitled")


def _parse_dt(raw: object) -> datetime | None:
    """Parse an ISO-8601 string to an aware UTC datetime; ``None`` if unparseable."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _recency_weight(when: datetime | None, now: datetime, fresh_days: int) -> float:
    """1.0 within ``fresh_days``, decaying linearly to 0 at ``2 * fresh_days``."""
    if when is None:
        return 0.0
    days = (now - when).days
    if days <= fresh_days:
        return 1.0
    return max(0.0, 1.0 - (days - fresh_days) / fresh_days)


def _is_descriptive(name: object) -> bool:
    """A photo filename is descriptive if it isn't a bare camera/screenshot dump."""
    if not isinstance(name, str):
        return False
    stem = name.strip().lower()
    if len(stem) < 10:
        return False
    return not stem.startswith(_GENERIC_PHOTO_PREFIXES)


# --------------------------------------------------------------------------- #
# Per-signal scorers — each returns (score 0..100, detail dict, action | None)  #
# --------------------------------------------------------------------------- #

ScoreResult = tuple[float, dict, str | None]


def _score_category(p: dict, now: datetime) -> ScoreResult:
    primary = p.get("primary_category")
    secondary = p.get("secondary_categories") or []
    score = (60.0 if primary else 0.0) + min(len(secondary), 2) * 20.0
    detail = {"primary_category": primary, "secondary_count": len(secondary)}
    if not primary:
        action = (
            "Set a specific primary category — it is the single strongest signal "
            "AI uses to decide which local queries your business matches."
        )
    elif not secondary:
        action = (
            "Add 1–2 secondary categories to widen the range of prompts AI can "
            "match you to without diluting your primary category."
        )
    else:
        action = None
    return min(score, 100.0), detail, action


def _score_products_services(p: dict, now: datetime, target: int = 5) -> ScoreResult:
    count = len(p.get("services") or []) + len(p.get("products") or [])
    score = min(count / target, 1.0) * 100.0
    detail = {"count": count, "target": target}
    action = (
        f"List at least {target} products/services (you have {count}); AI pulls "
        "from this catalog to answer 'best …' and 'who does …' prompts."
        if count < target
        else None
    )
    return score, detail, action


def _score_nap(p: dict, now: datetime) -> ScoreResult:
    nap = p.get("nap_consistency") or {}
    checked = nap.get("directories_checked")
    if not checked:
        detail = {"directories_checked": 0, "mismatches": None}
        return (
            0.0,
            detail,
            "Run an entity-consistency scan — your NAP has never been verified "
            "across directories, a core trust signal AI cross-checks.",
        )
    mismatches = int(nap.get("mismatches") or 0)
    score = max(0.0, (checked - mismatches) / checked) * 100.0
    detail = {"directories_checked": checked, "mismatches": mismatches}
    action = (
        f"Fix {mismatches} NAP inconsistency(ies) across directories — AI treats "
        "mismatched name/address/phone as a verification failure."
        if mismatches > 0
        else None
    )
    return score, detail, action


def _score_reviews(p: dict, now: datetime, fresh_days: int = 30) -> ScoreResult:
    r = p.get("reviews") or {}
    count = int(r.get("count") or 0)
    rating = r.get("average_rating")
    last = _parse_dt(r.get("last_review_at"))
    coverage = min(count / 25, 1.0)
    recency = _recency_weight(last, now, fresh_days)
    sentiment = (float(rating) / 5.0) if rating is not None else 0.0
    score = (0.4 * coverage + 0.3 * recency + 0.3 * sentiment) * 100.0
    detail = {
        "count": count,
        "average_rating": rating,
        "last_review_at": r.get("last_review_at"),
    }
    if count == 0 or recency == 0.0:
        action = (
            "Launch an equal-send review-request campaign to all eligible "
            "customers — recent reviews are a primary freshness signal for AI."
        )
    elif count < 25:
        action = (
            f"Grow review coverage (you have {count}); a deeper, recent review "
            "corpus gives AI more to cite and summarize."
        )
    else:
        action = None
    return score, detail, action


def _score_photos(p: dict, now: datetime, fresh_days: int = 90) -> ScoreResult:
    photos = p.get("photos") or []
    count = len(photos)
    coverage = min(count / 10, 1.0)
    dates = [d for d in (_parse_dt(ph.get("uploaded_at")) for ph in photos) if d]
    recency = _recency_weight(max(dates), now, fresh_days) if dates else 0.0
    named = sum(1 for ph in photos if _is_descriptive(ph.get("name")))
    naming = (named / count) if count else 0.0
    score = (0.4 * coverage + 0.3 * recency + 0.3 * naming) * 100.0
    detail = {"count": count, "descriptive_named": named}
    if count == 0 or recency == 0.0:
        action = (
            "Upload fresh, descriptively-named photos — recent imagery is a "
            "Vision-AI signal of an active, real business."
        )
    elif naming < 1.0:
        action = (
            f"Rename {count - named} generically-named photo(s) with descriptive, "
            "keyword-relevant filenames so Vision-AI can read them."
        )
    else:
        action = None
    return score, detail, action


def _score_qanda(p: dict, now: datetime, target: int = 5) -> ScoreResult:
    qa = p.get("qanda") or {}
    answered = int(qa.get("answered") or 0)
    total = int(qa.get("total") or answered)
    coverage = min(answered / target, 1.0)
    ratio = (answered / total) if total else 0.0
    score = (0.6 * coverage + 0.4 * ratio) * 100.0
    detail = {"answered": answered, "total": total}
    if total > answered:
        action = (
            f"Answer {total - answered} open question(s) — Q&A answers feed "
            "conversational AI responses about your business directly."
        )
    elif answered < target:
        action = (
            f"Seed and answer at least {target} common questions (you have "
            f"{answered}) to cover the prompts customers actually ask AI."
        )
    else:
        action = None
    return score, detail, action


def _score_posts(p: dict, now: datetime, fresh_days: int = 14) -> ScoreResult:
    last = _parse_dt(p.get("last_post_at"))
    detail = {"last_post_at": p.get("last_post_at")}
    if last is None:
        return (
            0.0,
            detail,
            "Publish a GBP post — post freshness signals a current, operating "
            "business to AI; you have no posts on record.",
        )
    days = (now - last).days
    score = _recency_weight(last, now, fresh_days) * 100.0
    action = (
        f"Publish a fresh GBP post — your last post was {days} days ago and "
        "stale post activity reads as an inactive profile."
        if days > fresh_days
        else None
    )
    return score, detail, action


def _score_attributes(p: dict, now: datetime, target: int = 5) -> ScoreResult:
    attrs = p.get("attributes") or []
    count = len(attrs)
    score = min(count / target, 1.0) * 100.0
    detail = {"count": count, "target": target}
    action = (
        f"Add {target - count} more attribute(s) (you have {count}); structured "
        "attributes give AI concrete facts to cite about your business."
        if count < target
        else None
    )
    return score, detail, action


# --------------------------------------------------------------------------- #
# Signal registry — weights sum to 100 so the weighted mean is itself 0..100.   #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _SignalDef:
    key: str
    label: str
    weight: float
    scorer: Callable[[dict, datetime], ScoreResult]


SIGNALS: tuple[_SignalDef, ...] = (
    _SignalDef("category_specificity", "Category specificity", 20.0, _score_category),
    _SignalDef("nap_consistency", "NAP consistency", 18.0, _score_nap),
    _SignalDef("products_services", "Products & services", 14.0, _score_products_services),
    _SignalDef("review_signals", "Review recency & sentiment", 14.0, _score_reviews),
    _SignalDef("photo_signals", "Photo recency & naming", 10.0, _score_photos),
    _SignalDef("qanda_coverage", "Q&A coverage", 9.0, _score_qanda),
    _SignalDef("post_freshness", "Post freshness", 9.0, _score_posts),
    _SignalDef("attributes", "Attributes", 6.0, _score_attributes),
)

_TOTAL_WEIGHT = sum(s.weight for s in SIGNALS)  # 100.0


def _priority(impact: float) -> str:
    """Bucket an impact (recoverable overall points) into a severity label."""
    if impact >= 10.0:
        return "high"
    if impact >= 5.0:
        return "medium"
    return "low"


def audit_ai_readiness(
    profile: dict | None,
    now: datetime | None = None,
    signals: Sequence[_SignalDef] = SIGNALS,
) -> AiReadinessReport:
    """Score a profile's GEO signals and return prioritized actions (GEO-7..GEO-9).

    Args:
        profile: The location's ``profile_data_live`` dict (``None`` → empty,
            which scores every signal at its floor and recommends every fix).
        now: Reference time for recency math; defaults to the current UTC time.
            Pass a fixed value for deterministic tests.
        signals: The signal definitions to evaluate (override only in tests).

    Returns:
        An :class:`AiReadinessReport` whose ``overall_score`` is the weighted mean
        of the per-signal scores and whose ``recommendations`` are sorted by
        descending recoverable impact (ties broken by signal key for stability).
    """
    profile = profile or {}
    now = now or datetime.now(tz=timezone.utc)

    scored: list[SignalScore] = []
    for sig in signals:
        score, detail, action = sig.scorer(profile, now)
        scored.append(
            SignalScore(
                key=sig.key,
                label=sig.label,
                weight=sig.weight,
                score=round(score, 2),
                detail=detail,
                action=action,
            )
        )

    total_weight = sum(s.weight for s in scored) or 1.0
    overall = round(sum(s.weight * s.score for s in scored) / total_weight, 2)

    recommendations: list[Recommendation] = []
    for s in scored:
        if s.action is None or s.score >= 100.0:
            continue
        impact = round(s.weight * (100.0 - s.score) / 100.0, 2)
        recommendations.append(
            Recommendation(
                signal=s.key,
                action=s.action,
                priority=_priority(impact),
                impact_points=impact,
            )
        )
    # Highest-leverage fix first; key as a stable tie-breaker (GEO-9).
    recommendations.sort(key=lambda r: (-r.impact_points, r.signal))

    return AiReadinessReport(
        overall_score=overall,
        signals=scored,
        recommendations=recommendations,
    )
