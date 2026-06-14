"""Structural guarantee: reverts are event-driven, never timer-driven (P4A-2).

CLAUDE.md hard rule: do NOT build unsupervised timer-based corrective writes to
critical fields. LocateX's silent 30-minute auto-revert is exactly what this ticket
replaces. This test fails the build if anyone reintroduces a scheduled/timed
corrective write into the protection package — the "structurally absent" half of
the guarantee (mirrors tests/compliance/test_no_sentiment_routing.py).

A revert may only be reached through ``ProtectionService.process_change`` (called by
the monitor when a change is *already* detected) or the human-confirmed
``restore_field`` — never from a clock.
"""
import io
import tokenize
from pathlib import Path

_PROTECTION = Path(__file__).resolve().parents[2] / "app" / "protection"

# Identifiers that would indicate a timer/scheduler driving writes from this package.
# (Comments/docstrings are excluded via tokenisation, so prose explaining the *ban*
# does not trip the guard.)
FORBIDDEN_TOKENS = (
    "celery_app",
    "shared_task",
    "beat_schedule",
    "crontab",
    "periodic_task",
    "apply_async",
    "countdown",
    "eta",
    "Timer",
    "sleep",
    "set_interval",
    "schedule",
)


def _identifiers(source: str) -> set[str]:
    names: set[str] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.NAME:
                names.add(tok.string)
    except tokenize.TokenError:  # pragma: no cover
        pass
    return names


def test_protection_package_has_no_scheduler_or_timer():
    offenders: list[str] = []
    for path in _PROTECTION.rglob("*.py"):
        identifiers = _identifiers(path.read_text(encoding="utf-8"))
        for name in identifiers:
            if name in FORBIDDEN_TOKENS:
                offenders.append(f"{path.name} -> {name}")
    assert not offenders, (
        "Timer/scheduler reference found in app/protection — reverts must be "
        f"event-driven, never on a clock (CLAUDE.md): {offenders}"
    )


def test_protection_registers_no_celery_task():
    """Importing the package must not register any Celery task (no @task anywhere)."""
    from app.core.celery_app import celery_app

    import app.protection  # noqa: F401 — force import side effects

    protection_tasks = [
        name for name in celery_app.tasks if "protection" in name.lower()
    ]
    assert protection_tasks == [], (
        f"app.protection must register no Celery tasks; found {protection_tasks}"
    )
