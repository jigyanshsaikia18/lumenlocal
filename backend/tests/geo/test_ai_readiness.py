"""P2C-3: AI-readiness audit + recommendation engine (PRD GEO-7..GEO-9).

Pure-function tests — no DB, no HTTP. The headline acceptance case
(``test_known_gaps_return_expected_prioritized_actions``) feeds a fixture profile
with deliberately known gaps and asserts both the overall score and the exact,
impact-ordered recommendation list, since "prioritized, profile-specific actions"
is the whole deliverable of GEO-9.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.geo.ai_readiness import audit_ai_readiness

NOW = datetime(2026, 6, 16, tzinfo=timezone.utc)


# A profile with a known gap in every signal, chosen so each signal's score and
# therefore its recoverable impact is hand-computable (see the asserts below).
GAPPY_PROFILE = {
    # category: no primary, no secondary  → score 0   (weight 20 → impact 20.0)
    "primary_category": None,
    "secondary_categories": [],
    # nap: 4 of 10 directories mismatch    → score 60  (weight 18 → impact 7.2)
    "nap_consistency": {"directories_checked": 10, "mismatches": 4},
    # products+services: 2 of target 5     → score 40  (weight 14 → impact 8.4)
    "services": [{"name": "Oil change"}, {"name": "Brake repair"}],
    "products": [],
    # reviews: none                         → score 0   (weight 14 → impact 14.0)
    "reviews": {"count": 0},
    # photos: none                          → score 0   (weight 10 → impact 10.0)
    "photos": [],
    # q&a: 1 answered of 3                  → score 25.33 (weight 9 → impact 6.72)
    "qanda": {"answered": 1, "total": 3},
    # posts: none                           → score 0   (weight 9 → impact 9.0)
    "last_post_at": None,
    # attributes: none                      → score 0   (weight 6 → impact 6.0)
    "attributes": [],
}


def test_known_gaps_return_expected_prioritized_actions():
    """The flagship acceptance test: known gaps → expected ranked actions (GEO-9)."""
    report = audit_ai_readiness(GAPPY_PROFILE, now=NOW)

    # Overall = weighted mean of per-signal scores:
    #   nap 18*60 + products 14*40 + qanda 9*25.33  = 1080 + 560 + 227.97 = 1867.97
    #   everything else scores 0  →  1867.97 / 100 = 18.68
    assert report.overall_score == 18.68

    # Every signal has a gap, so all eight produce a recommendation,
    # ordered by descending recoverable impact (ties broken by signal key).
    ordered = [(r.signal, r.impact_points, r.priority) for r in report.recommendations]
    assert ordered == [
        ("category_specificity", 20.0, "high"),
        ("review_signals", 14.0, "high"),
        ("photo_signals", 10.0, "high"),
        ("post_freshness", 9.0, "medium"),
        ("products_services", 8.4, "medium"),
        ("nap_consistency", 7.2, "medium"),
        ("qanda_coverage", 6.72, "medium"),
        ("attributes", 6.0, "medium"),
    ]


def test_review_recommendation_is_compliant_equal_send_only():
    """Compliance (CLAUDE.md): the review action never proposes gating/targeting."""
    report = audit_ai_readiness(GAPPY_PROFILE, now=NOW)
    review = next(r for r in report.recommendations if r.signal == "review_signals")
    assert "equal-send" in review.action.lower()
    # No sentiment-routing / gating language may ever appear.
    for banned in ("happy", "gate", "gating", "satisfied only", "filter out"):
        assert banned not in review.action.lower()


def test_empty_profile_scores_zero_and_recommends_every_signal():
    """A blank profile floors every signal and surfaces a fix for each (GEO-7)."""
    report = audit_ai_readiness({}, now=NOW)
    assert report.overall_score == 0.0
    assert len(report.recommendations) == len(report.signals) == 8
    # Category is the heaviest signal → always the top action when fully missing.
    assert report.recommendations[0].signal == "category_specificity"


def test_strong_profile_scores_100_with_no_recommendations():
    """A complete, fresh profile is fully ready → 100.0 and an empty action list."""
    strong = {
        "primary_category": "Auto Repair Shop",
        "secondary_categories": ["Brake Shop", "Oil Change Service"],
        "nap_consistency": {"directories_checked": 12, "mismatches": 0},
        "services": [{"name": f"svc{i}"} for i in range(6)],
        "products": [],
        "reviews": {"count": 80, "average_rating": 5.0, "last_review_at": "2026-06-12"},
        "photos": [
            {"name": "front-of-shop-exterior.jpg", "uploaded_at": "2026-06-10"}
            for _ in range(12)
        ],
        "qanda": {"answered": 6, "total": 6},
        "last_post_at": "2026-06-14",
        "attributes": ["wheelchair_accessible", "wifi", "parking", "appointments", "card"],
    }
    report = audit_ai_readiness(strong, now=NOW)
    assert report.overall_score == 100.0
    assert report.recommendations == []


def test_recommendations_sorted_by_descending_impact():
    """Whatever the profile, recommendations are monotonically non-increasing impact."""
    report = audit_ai_readiness(GAPPY_PROFILE, now=NOW)
    impacts = [r.impact_points for r in report.recommendations]
    assert impacts == sorted(impacts, reverse=True)


def test_overall_score_is_weighted_mean_of_signal_scores():
    """Overall must equal sum(weight*score)/sum(weight) over the reported signals."""
    report = audit_ai_readiness(GAPPY_PROFILE, now=NOW)
    total_w = sum(s.weight for s in report.signals)
    expected = round(sum(s.weight * s.score for s in report.signals) / total_w, 2)
    assert report.overall_score == expected


def test_stale_post_is_flagged_with_day_count():
    """A post older than the freshness window yields a profile-specific action."""
    # 40 days before NOW → past the 14-day window, well inside the linear decay.
    report = audit_ai_readiness({"last_post_at": "2026-05-07"}, now=NOW)
    post = next(r for r in report.recommendations if r.signal == "post_freshness")
    assert "40 days ago" in post.action


def test_malformed_profile_cannot_exceed_100():
    """Untrusted profile_data_live (rating>5, answered>total) must stay clamped 0..100.

    Regression for the score-overflow defect: per-signal scores are clamped so a
    malformed JSONB profile can never push a signal — or the weighted overall —
    above 100 (or below 0).
    """
    malformed = {
        "primary_category": "Cafe",
        "secondary_categories": ["a", "b"],
        "reviews": {"count": 1000, "average_rating": 9, "last_review_at": "2026-06-15"},
        "qanda": {"answered": 50, "total": 1},
    }
    report = audit_ai_readiness(malformed, now=NOW)
    assert 0.0 <= report.overall_score <= 100.0
    for s in report.signals:
        assert 0.0 <= s.score <= 100.0, f"{s.key} score out of range: {s.score}"
