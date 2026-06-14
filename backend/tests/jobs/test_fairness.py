"""Unit tests for the per-tenant fairness gate."""
from app.jobs import fairness
from app.jobs.store import InMemoryStore

TTL = 3600


def test_acquire_grants_up_to_cap(store: InMemoryStore):
    cap = 3
    assert [fairness.acquire(store, "t1", cap, TTL) for _ in range(cap)] == [True, True, True]
    # One past the cap is refused...
    assert fairness.acquire(store, "t1", cap, TTL) is False
    # ...and the refusal does not leak a slot: still exactly `cap` in flight.
    assert fairness.in_flight(store, "t1") == cap


def test_release_frees_a_slot(store: InMemoryStore):
    cap = 1
    assert fairness.acquire(store, "t1", cap, TTL) is True
    assert fairness.acquire(store, "t1", cap, TTL) is False
    fairness.release(store, "t1")
    # Slot returned, so a new acquire succeeds again.
    assert fairness.acquire(store, "t1", cap, TTL) is True


def test_tenants_are_isolated(store: InMemoryStore):
    cap = 1
    assert fairness.acquire(store, "t1", cap, TTL) is True
    # A different tenant has its own counter and is unaffected by t1's cap.
    assert fairness.acquire(store, "t2", cap, TTL) is True


def test_release_never_goes_negative(store: InMemoryStore):
    fairness.release(store, "t1")
    fairness.release(store, "t1")
    assert fairness.in_flight(store, "t1") == 0
    # And the counter is usable again afterwards.
    assert fairness.acquire(store, "t1", 1, TTL) is True
