"""Unit tests for the dead-letter queue."""
from app.jobs import dead_letter
from app.jobs.store import InMemoryStore


def _record(store, **over):
    base = dict(
        task_name="app.jobs.example.echo",
        task_id="abc",
        tenant_id="t1",
        args=(),
        kwargs={"message": "hi"},
        exc=RuntimeError("boom"),
    )
    base.update(over)
    return dead_letter.record(store, **base)


def test_record_captures_failure_metadata(store: InMemoryStore):
    entry = _record(store)
    assert entry["task_name"] == "app.jobs.example.echo"
    assert entry["tenant_id"] == "t1"
    assert entry["exc_type"] == "RuntimeError"
    assert entry["exc"] == "boom"
    assert "failed_at" in entry


def test_record_serialises_unjsonable_args_via_repr(store: InMemoryStore):
    # A UUID-like object isn't JSON-serialisable; repr() keeps the DLQ robust.
    obj = object()
    entry = _record(store, args=(obj,), kwargs={"o": obj})
    assert entry["args"] == [repr(obj)]
    assert entry["kwargs"] == {"o": repr(obj)}


def test_read_returns_records_oldest_first(store: InMemoryStore):
    _record(store, exc=RuntimeError("first"))
    _record(store, exc=RuntimeError("second"))
    assert dead_letter.depth(store) == 2
    read = dead_letter.read(store)
    assert [r["exc"] for r in read] == ["first", "second"]


def test_read_respects_limit(store: InMemoryStore):
    for i in range(5):
        _record(store, exc=RuntimeError(str(i)))
    assert len(dead_letter.read(store, limit=2)) == 2
