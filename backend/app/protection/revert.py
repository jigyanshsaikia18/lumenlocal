"""The bounded-revert policy — pure decision over one detected change (P4A-2).

This is the safe replacement for LocateX's silent timer-based auto-revert. Given a
location's ``revert_mode`` and a :class:`~app.protection.changes.ProfileChange`, it
decides the corrective *action* — and nothing else. It performs no I/O and never
writes to Google; that belongs to :class:`app.protection.service.ProtectionService`,
which routes any write through the mandatory Policy Compliance Gateway. Splitting
the decision out (exactly like ``app.compliance.engine`` vs ``…gateway``) is what
makes every branch of the compliance guarantee unit-testable in isolation.

The three modes (schema §4 ``locations.revert_mode``, PRD §7 P-2a):

* ``alert_only`` *(default)* — detect + alert; **never** an automated write.
* ``auto_revert_critical`` — automatically restore the baseline **only** for a
  narrow set of critical fields (:data:`~app.protection.fields.AUTO_REVERT_CRITICAL_FIELDS`)
  and **only** on an unambiguous high-severity change; everything else falls back
  to an alert. The corrective write is still rate-limited, audited, and gateway-checked
  downstream.
* ``off`` — no corrective action at all.

There is intentionally **no timer here, and no scheduled task anywhere in this
package**: a revert is only ever decided in response to an already-detected change,
never on a clock — see ``tests/protection/test_no_timer_revert.py``.
"""
from __future__ import annotations

from app.protection.changes import ProfileChange
from app.protection.fields import AUTO_REVERT_CRITICAL_FIELDS, SEVERITY_HIGH

# --- revert_mode values (mirror locations.revert_mode, schema §4) -----------------
REVERT_MODE_ALERT_ONLY = "alert_only"
REVERT_MODE_AUTO_CRITICAL = "auto_revert_critical"
REVERT_MODE_OFF = "off"

VALID_REVERT_MODES = frozenset(
    {REVERT_MODE_ALERT_ONLY, REVERT_MODE_AUTO_CRITICAL, REVERT_MODE_OFF}
)

# --- corrective actions the policy can choose -------------------------------------
ACTION_NONE = "none"  # off — do nothing
ACTION_ALERT = "alerted"  # notify a human; no write (matches profile_change_events)
ACTION_REVERT = "reverted"  # restore the baseline value through the gateway + writer


def is_auto_revertible(change: ProfileChange) -> bool:
    """True only for a change narrow enough to correct without a human.

    Both conditions are required, and together they are the structural guarantee
    that an automated revert can touch *only allowed fields*:

    * the field is one of the bounded critical fields (name / category / phone /
      pin) — a non-critical field can never be auto-reverted; and
    * the monitor classified the change ``high`` severity — i.e. unambiguous
      (e.g. a pin moved past the threshold, the name cleared). A low/medium change
      to even a critical field is too ambiguous to write back automatically.
    """
    return (
        change.field in AUTO_REVERT_CRITICAL_FIELDS
        and change.severity == SEVERITY_HIGH
    )


def decide(mode: str, change: ProfileChange) -> str:
    """Return the corrective action for ``change`` under ``mode``.

    * ``auto_revert_critical`` + an auto-revertible change → :data:`ACTION_REVERT`.
    * ``off`` → :data:`ACTION_NONE`.
    * anything else (``alert_only``, or ``auto_revert_critical`` on a change that is
      not unambiguously critical) → :data:`ACTION_ALERT`.

    Note the ordering: only ``auto_revert_critical`` can ever yield a write, and only
    via :func:`is_auto_revertible`. ``off`` short-circuits to no action even for a
    malicious critical change — the location's owner opted out entirely.

    Raises:
        ValueError: if ``mode`` is not a recognised ``revert_mode``.
    """
    if mode not in VALID_REVERT_MODES:
        raise ValueError(
            f"unknown revert_mode {mode!r}; expected one of {sorted(VALID_REVERT_MODES)}"
        )
    if mode == REVERT_MODE_AUTO_CRITICAL and is_auto_revertible(change):
        return ACTION_REVERT
    if mode == REVERT_MODE_OFF:
        return ACTION_NONE
    return ACTION_ALERT
