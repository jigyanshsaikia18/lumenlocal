"""Integration tests for the example task running through the full framework.

Celery runs eager (see conftest) so these exercise the real ``TenantTask.__call__``
path — idempotency, fairness, retries and dead-lettering — without any broker.
"""
from app.jobs import dead_letter
from app.jobs.example import add, echo
from app.jobs.store import get_store


def test_add_enqueues_and_runs():
    """The headline acceptance: a task enqueues and runs, returning its result."""
    result = add.delay(2, 3)
    assert result.get() == 5


def test_tenant_task_returns_payload_and_frees_slot():
    from app.jobs import fairness

    result = echo.delay("hello", tenant_id="t1").get()
    assert result == {"message": "hello", "tenant_id": "t1"}
    # The in-flight slot taken for the run was released on completion.
    assert fairness.in_flight(get_store(), "t1") == 0


def test_duplicate_idempotency_key_is_skipped():
    first = echo.delay("once", idempotency_key="k1").get()
    assert first == {"message": "once", "tenant_id": None}

    # Same key again: the body is not re-run; a duplicate envelope comes back.
    second = echo.delay("twice", idempotency_key="k1").get()
    assert second["status"] == "duplicate"
    assert second["idempotency_key"] == "k1"


def test_distinct_idempotency_keys_both_run():
    a = echo.delay("a", idempotency_key="ka").get()
    b = echo.delay("b", idempotency_key="kb").get()
    assert a["message"] == "a"
    assert b["message"] == "b"


def test_transient_failures_are_retried_then_succeed():
    # Fails twice (within the 3-retry budget) then returns normally.
    result = echo.delay("eventually", fail_times=2).get()
    assert result["message"] == "eventually"


def test_exhausted_retries_land_in_dead_letter():
    # Always fails: retries are spent and the attempt is parked on the DLQ.
    result = echo.delay("doomed", tenant_id="t9", fail_times=99)
    try:
        result.get()
    except RuntimeError:
        pass  # eager mode propagates the final failure; we only care about the DLQ

    parked = dead_letter.read(get_store())
    assert len(parked) == 1
    assert parked[0]["task_name"].endswith("example.echo")
    assert parked[0]["tenant_id"] == "t9"
