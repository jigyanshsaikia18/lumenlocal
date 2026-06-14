"""The mock provider's fetch/query behavior (P2C-1): offline, deterministic, and
no live calls leak through the base interface before P2C-2."""
import pytest

from app.geo.ai import AiSearchProvider, MockAiSearchProvider, Provider
from app.geo.ai.records import AiVisibilityRecord


def test_query_runs_end_to_end_offline():
    rec = MockAiSearchProvider().query("best pizza near me", business_name="Riverside Bistro")
    assert isinstance(rec, AiVisibilityRecord)
    assert rec.provider is Provider.AI_OVERVIEWS


def test_fetch_is_deterministic_for_a_prompt():
    p = MockAiSearchProvider()
    assert p.fetch("best dentist in Brooklyn") == p.fetch("best dentist in Brooklyn")


def test_query_is_deterministic():
    a = MockAiSearchProvider().query("plumber near me", business_name="Summit Auto Works")
    b = MockAiSearchProvider().query("plumber near me", business_name="Summit Auto Works")
    assert a == b


def test_different_prompts_can_differ():
    p = MockAiSearchProvider()
    assert p.fetch("best coffee") != p.fetch("best tacos")


def test_canned_response_is_returned_verbatim():
    canned = {"answer": "", "businesses": [{"name": "Acme Co", "rank": 1}], "sources": []}
    p = MockAiSearchProvider(canned_response=canned)
    assert p.fetch("anything") is canned
    rec = p.query("anything", business_name="Acme Co")
    assert rec.mentioned is True
    assert rec.prominence == 1


def test_base_fetch_refuses_live_calls():
    # A bare adapter must not silently reach a provider before P2C-2 wires real calls.
    class BareProvider(AiSearchProvider):
        provider = Provider.GROK

        def normalize(self, raw, *, business_name):  # pragma: no cover - unused
            raise AssertionError("normalize should not be reached")

    with pytest.raises(NotImplementedError):
        BareProvider().query("anything", business_name="x")
