"""Profile protection — bounded revert + one-click restore (P4A-2, PRD §7).

The safe replacement for silent timer-based auto-revert. A detected
:class:`ProfileChange` is evaluated by the **pure** policy :func:`decide` against a
location's ``revert_mode``; :class:`ProtectionService` then executes the result —
``alert_only`` (never writes), ``auto_revert_critical`` (bounded, rate-limited,
gateway-checked write of a narrow critical-field set only), or ``off`` (nothing).
Every corrective write is an ``ExternalWrite`` pushed through the mandatory Policy
Compliance Gateway and appended to ``profile_change_events``. There is **no timer
and no scheduled task in this package** — reverts are event-driven only.
"""
from app.protection.changes import ProfileChange
from app.protection.fields import (
    AUTO_REVERT_CRITICAL_FIELDS,
    PIN_MOVE_THRESHOLD_METERS,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    pin_move_is_critical,
)
from app.protection.rate_limit import (
    DEFAULT_MAX_REVERTS,
    DEFAULT_WINDOW_SECONDS,
    InMemoryRevertRateLimiter,
    RevertRateLimiter,
)
from app.protection.recorder import (
    ChangeEventRecorder,
    InMemoryChangeEventRecorder,
    RevertOutcome,
    SqlAlchemyChangeEventRecorder,
)
from app.protection.revert import (
    ACTION_ALERT,
    ACTION_NONE,
    ACTION_REVERT,
    REVERT_MODE_ALERT_ONLY,
    REVERT_MODE_AUTO_CRITICAL,
    REVERT_MODE_OFF,
    VALID_REVERT_MODES,
    decide,
    is_auto_revertible,
)
from app.protection.service import (
    BaselineUnavailableError,
    ProtectionService,
    RevertResult,
)
from app.protection.writer import ProfileWriter

__all__ = [
    "ACTION_ALERT",
    "ACTION_NONE",
    "ACTION_REVERT",
    "AUTO_REVERT_CRITICAL_FIELDS",
    "BaselineUnavailableError",
    "ChangeEventRecorder",
    "DEFAULT_MAX_REVERTS",
    "DEFAULT_WINDOW_SECONDS",
    "InMemoryChangeEventRecorder",
    "InMemoryRevertRateLimiter",
    "PIN_MOVE_THRESHOLD_METERS",
    "ProfileChange",
    "ProfileWriter",
    "ProtectionService",
    "REVERT_MODE_ALERT_ONLY",
    "REVERT_MODE_AUTO_CRITICAL",
    "REVERT_MODE_OFF",
    "RevertOutcome",
    "RevertRateLimiter",
    "RevertResult",
    "SEVERITY_HIGH",
    "SEVERITY_LOW",
    "SEVERITY_MEDIUM",
    "SqlAlchemyChangeEventRecorder",
    "VALID_REVERT_MODES",
    "decide",
    "is_auto_revertible",
    "pin_move_is_critical",
]
