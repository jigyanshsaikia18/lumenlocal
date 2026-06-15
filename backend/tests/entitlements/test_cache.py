"""P1C-2: the TTL cache memoises resolution but lets a toggle take effect in time.

A fake clock makes the timing deterministic: within the TTL the loader is not
called again (caching); past it, resolution refreshes (so a toggle propagates
within the window, PRD §5 FT-2); and an explicit invalidation forces an immediate
refresh ahead of the TTL.
"""
from uuid import uuid4

from app.entitlements.cache import TtlEntitlementCache
from app.entitlements.resolver import ResolvedFeature, SOURCE_CLIENT, SOURCE_DEFAULT


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_loader(value):
    """A loader that records its call count and returns a 1-feature resolved set."""
    calls = {"n": 0}

    def loader(client_id, location_id):
        calls["n"] += 1
        return {"geogrid": ResolvedFeature("geogrid", value[0], value[1])}

    return loader, calls


def test_within_ttl_serves_cached_value_without_reloading():
    clock = FakeClock()
    cache = TtlEntitlementCache(ttl_seconds=60, clock=clock)
    loader, calls = make_loader([True, SOURCE_DEFAULT])
    cid = uuid4()

    first = cache.resolve(cid, None, loader)
    clock.advance(59)
    second = cache.resolve(cid, None, loader)

    assert first is second
    assert calls["n"] == 1  # loader hit once; the second read came from cache


def test_past_ttl_reresolves():
    clock = FakeClock()
    cache = TtlEntitlementCache(ttl_seconds=60, clock=clock)
    loader, calls = make_loader([True, SOURCE_DEFAULT])
    cid = uuid4()

    cache.resolve(cid, None, loader)
    clock.advance(61)  # TTL elapsed → must reload
    cache.resolve(cid, None, loader)

    assert calls["n"] == 2


def test_invalidate_client_forces_immediate_refresh():
    clock = FakeClock()
    cache = TtlEntitlementCache(ttl_seconds=600, clock=clock)
    cid = uuid4()
    state = {"enabled": True, "source": SOURCE_DEFAULT}

    def loader(client_id, location_id):
        return {"geogrid": ResolvedFeature("geogrid", state["enabled"], state["source"])}

    assert cache.resolve(cid, None, loader)["geogrid"].enabled is True
    # Simulate a toggle write: state changes, cache invalidated for this client.
    state["enabled"], state["source"] = False, SOURCE_CLIENT
    cache.invalidate_client(cid)

    refreshed = cache.resolve(cid, None, loader)["geogrid"]
    assert refreshed.enabled is False
    assert refreshed.source == SOURCE_CLIENT


def test_invalidate_client_only_evicts_that_client():
    clock = FakeClock()
    cache = TtlEntitlementCache(ttl_seconds=600, clock=clock)
    a, b = uuid4(), uuid4()
    loader_a, calls_a = make_loader([True, SOURCE_DEFAULT])
    loader_b, calls_b = make_loader([True, SOURCE_DEFAULT])

    cache.resolve(a, None, loader_a)
    cache.resolve(b, None, loader_b)
    cache.invalidate_client(a)

    cache.resolve(a, None, loader_a)  # evicted → reloads
    cache.resolve(b, None, loader_b)  # untouched → still cached
    assert calls_a["n"] == 2
    assert calls_b["n"] == 1


def test_location_scope_is_cached_separately_from_client_scope():
    clock = FakeClock()
    cache = TtlEntitlementCache(ttl_seconds=600, clock=clock)
    cid, lid = uuid4(), uuid4()
    loader, calls = make_loader([True, SOURCE_DEFAULT])

    cache.resolve(cid, None, loader)
    cache.resolve(cid, lid, loader)  # different key → separate load
    assert calls["n"] == 2

    # invalidate_client drops both the client- and location-scoped entries.
    cache.invalidate_client(cid)
    cache.resolve(cid, lid, loader)
    assert calls["n"] == 3
