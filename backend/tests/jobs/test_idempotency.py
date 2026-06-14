"""Unit tests for the idempotency ledger."""
from app.jobs import idempotency
from app.jobs.store import InMemoryStore

TTL = 3600


def test_first_claim_succeeds_duplicate_fails(store: InMemoryStore):
    assert idempotency.claim(store, "scan:1", TTL) is True
    assert idempotency.state(store, "scan:1") == idempotency.PENDING
    # A second submission of the same key while still claimed is a duplicate.
    assert idempotency.claim(store, "scan:1", TTL) is False


def test_mark_done_keeps_suppressing_duplicates(store: InMemoryStore):
    idempotency.claim(store, "scan:1", TTL)
    idempotency.mark_done(store, "scan:1", TTL)
    assert idempotency.state(store, "scan:1") == idempotency.DONE
    # Even after completion, the key is remembered so late duplicates are skipped.
    assert idempotency.claim(store, "scan:1", TTL) is False


def test_release_allows_resubmission(store: InMemoryStore):
    idempotency.claim(store, "scan:1", TTL)
    idempotency.release(store, "scan:1")
    assert idempotency.state(store, "scan:1") is None
    # Released claim (e.g. after terminal failure) can be retaken.
    assert idempotency.claim(store, "scan:1", TTL) is True


def test_distinct_keys_are_independent(store: InMemoryStore):
    assert idempotency.claim(store, "a", TTL) is True
    assert idempotency.claim(store, "b", TTL) is True
