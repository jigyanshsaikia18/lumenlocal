"""Normalization contract (P2C-1): feed a sample provider response, assert the
common {provider, mentioned, prominence, cited_sources} record comes out right."""
import pytest

from app.geo.ai import AiVisibilityRecord, MockAiSearchProvider, Provider

# A representative provider answer: a synthesized blurb, a ranked business list,
# and cited sources in the two shapes providers use (objects + bare URL string).
SAMPLE_RESPONSE = {
    "answer": "For the best pizza nearby, locals point to a few standout spots.",
    "businesses": [
        {"name": "Tony's Pizzeria", "rank": 1},
        {"name": "Joe's Pizza Napoletana", "rank": 2},
        {"name": "Slice Corner", "rank": 3},
    ],
    "sources": [
        {"url": "https://www.yelp.com/biz/joes"},
        {"href": "https://www.tripadvisor.com/joes"},
        "https://www.google.com/maps/joes",
    ],
}


def test_normalizes_a_ranked_mention():
    rec = MockAiSearchProvider().normalize(SAMPLE_RESPONSE, business_name="Joe's Pizza")

    assert isinstance(rec, AiVisibilityRecord)
    assert rec.provider is Provider.AI_OVERVIEWS
    assert rec.mentioned is True
    # "Joe's Pizza" matched "Joe's Pizza Napoletana" at rank 2.
    assert rec.prominence == 2
    assert rec.cited_sources == (
        "https://www.yelp.com/biz/joes",
        "https://www.tripadvisor.com/joes",
        "https://www.google.com/maps/joes",
    )


def test_provider_label_is_carried_through():
    rec = MockAiSearchProvider(provider=Provider.PERPLEXITY).normalize(
        SAMPLE_RESPONSE, business_name="Tony's Pizzeria"
    )
    assert rec.provider is Provider.PERPLEXITY
    assert rec.prominence == 1


def test_not_mentioned_yields_false_and_none_prominence():
    rec = MockAiSearchProvider().normalize(SAMPLE_RESPONSE, business_name="Nonexistent Cafe")
    assert rec.mentioned is False
    assert rec.prominence is None
    # Sources are still captured even when the business is absent (GEO-5 signal).
    assert len(rec.cited_sources) == 3


def test_buried_mention_in_answer_only_is_mentioned_without_rank():
    raw = {
        "answer": "Honorable mention also goes to Joe's Pizza for late-night slices.",
        "businesses": [{"name": "Tony's Pizzeria", "rank": 1}],
        "sources": [],
    }
    rec = MockAiSearchProvider().normalize(raw, business_name="Joe's Pizza")
    assert rec.mentioned is True
    assert rec.prominence is None


def test_prominence_falls_back_to_position_without_explicit_rank():
    raw = {
        "answer": "",
        "businesses": [{"name": "Tony's"}, {"name": "Joe's Pizza"}],
    }
    rec = MockAiSearchProvider().normalize(raw, business_name="Joe's Pizza")
    assert rec.prominence == 2


def test_name_match_is_case_insensitive_and_substring():
    raw = {"businesses": [{"name": "JOE'S PIZZA NAPOLETANA", "rank": 5}]}
    rec = MockAiSearchProvider().normalize(raw, business_name="joe's pizza")
    assert rec.mentioned is True
    assert rec.prominence == 5


def test_sources_are_deduped_preserving_order_and_blanks_dropped():
    raw = {
        "businesses": [],
        "sources": [
            "https://a.com",
            {"url": "https://b.com"},
            "https://a.com",  # duplicate
            {"url": ""},       # blank
            {"nope": "x"},     # no url key
        ],
    }
    rec = MockAiSearchProvider().normalize(raw, business_name="anything")
    assert rec.cited_sources == ("https://a.com", "https://b.com")


def test_missing_keys_are_tolerated():
    rec = MockAiSearchProvider().normalize({}, business_name="Joe's Pizza")
    assert rec.mentioned is False
    assert rec.prominence is None
    assert rec.cited_sources == ()


def test_as_dict_is_jsonb_ready():
    rec = MockAiSearchProvider().normalize(SAMPLE_RESPONSE, business_name="Joe's Pizza")
    assert rec.as_dict() == {
        "provider": "ai_overviews",
        "mentioned": True,
        "prominence": 2,
        "cited_sources": [
            "https://www.yelp.com/biz/joes",
            "https://www.tripadvisor.com/joes",
            "https://www.google.com/maps/joes",
        ],
    }


@pytest.mark.parametrize("provider", list(Provider))
def test_every_provider_value_matches_db_enum(provider):
    # Values must equal the geo_ai_scans.provider strings in 04_Database_Schema.md.
    assert provider.value in {
        "ai_overviews",
        "ai_mode",
        "gemini",
        "chatgpt",
        "perplexity",
        "grok",
    }
