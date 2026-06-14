"""Unit tests for the in-memory store's Redis-shaped primitives."""
import time

from app.jobs.store import InMemoryStore


def test_incr_decr_round_trip(store: InMemoryStore):
    assert store.incr("c") == 1
    assert store.incr("c") == 2
    assert store.decr("c") == 1


def test_set_if_absent_is_atomic_first_write_wins(store: InMemoryStore):
    assert store.set_if_absent("k", "a") is True
    # A second claim on the same key fails and does not overwrite.
    assert store.set_if_absent("k", "b") is False
    assert store.get("k") == "a"


def test_delete_clears_value(store: InMemoryStore):
    store.set("k", "v")
    store.delete("k")
    assert store.get("k") is None


def test_ttl_expiry_is_honoured_lazily(store: InMemoryStore):
    store.set("k", "v", ttl=1)
    assert store.get("k") == "v"
    # Force the key past its TTL; the next read should treat it as gone.
    store._expiry["k"] = time.monotonic() - 1
    assert store.get("k") is None
    # An expired claim can be retaken.
    assert store.set_if_absent("k", "fresh") is True


def test_list_rpush_lrange_llen(store: InMemoryStore):
    store.rpush("q", "a")
    store.rpush("q", "b")
    assert store.llen("q") == 2
    assert store.lrange("q", 0, -1) == ["a", "b"]
    assert store.lrange("q", 0, 0) == ["a"]


def test_clear_drops_everything(store: InMemoryStore):
    store.set("k", "v")
    store.rpush("q", "a")
    store.clear()
    assert store.get("k") is None
    assert store.llen("q") == 0
