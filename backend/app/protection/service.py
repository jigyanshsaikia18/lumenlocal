"""The protection executor: turn a decision into a safe, audited corrective action.

:class:`ProtectionService` is the side-effecting layer over the pure policy in
:mod:`app.protection.revert` (the same split as ``app.compliance.gateway`` over
``…engine``). It has exactly two entry points and there is **no timer behind either
one** — both are invoked in response to something that already happened:

* :meth:`process_change` — called by the P4A-1 monitor when it detects a change.
  It asks the policy what to do and then, for a revert and a revert only, performs
  the bounded write: rate-limit gate → look up the baseline value → **mandatory
  ``PolicyGateway.guard``** → :class:`~app.protection.writer.ProfileWriter` →
  record. ``alert_only`` and ``off`` never reach the writer.
* :meth:`restore_field` — the human-confirmed *one-click reject/restore* (PRD §7
  P-2). Because a person initiated it, it works in any mode, but it still goes
  through the same gateway + writer + audit path — no write escapes the Policy
  Engine.

Every outbound restore is described as an ``ExternalWrite(ACTION_LISTING_EDIT)`` and
passed through the gateway *before* the writer is touched; if the gateway blocks
(422) the writer is never called and nothing is recorded as reverted — fail-closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.compliance import ACTION_LISTING_EDIT, ExternalWrite, PolicyGateway
from app.protection.changes import ProfileChange
from app.protection.fields import AUTO_REVERT_CRITICAL_FIELDS
from app.protection.rate_limit import RevertRateLimiter
from app.protection.recorder import ChangeEventRecorder, RevertOutcome
from app.protection.revert import (
    ACTION_ALERT,
    ACTION_NONE,
    ACTION_REVERT,
    decide,
)
from app.protection.writer import ProfileWriter


class BaselineUnavailableError(Exception):
    """A revert was authorised but the locked baseline has no value to restore.

    Raised before any external write is attempted, so the profile is left untouched
    (the change is surfaced as an alert by the caller instead).
    """


@dataclass(frozen=True)
class RevertResult:
    """Outcome of handling one change / restore request.

    ``action`` is one of the ``revert.ACTION_*`` strings. ``rate_limited`` is set
    when an otherwise-eligible auto-revert was downgraded to an alert because the
    location hit its revert cap.
    """

    action: str
    field: str
    rate_limited: bool = False


class ProtectionService:
    """Execute the bounded-revert policy with all the required safeguards."""

    def __init__(
        self,
        *,
        gateway: PolicyGateway,
        writer: ProfileWriter,
        rate_limiter: RevertRateLimiter,
        recorder: ChangeEventRecorder,
    ) -> None:
        self._gateway = gateway
        self._writer = writer
        self._rate_limiter = rate_limiter
        self._recorder = recorder

    # --- event-driven entry point ----------------------------------------

    def process_change(self, *, location: Any, change: ProfileChange) -> RevertResult:
        """Handle one detected change per the location's ``revert_mode``.

        ``location`` must expose ``id``, ``revert_mode`` and ``profile_data_locked``
        (the SQLAlchemy ``Location`` does). Returns a :class:`RevertResult`; raises
        :class:`~app.core.errors.APIError` (422) only if a revert would itself
        violate policy — in which case nothing was written.
        """
        action = decide(location.revert_mode, change)

        if action == ACTION_NONE:
            # off — the owner opted out; record nothing, write nothing.
            return RevertResult(ACTION_NONE, change.field)

        if action == ACTION_ALERT:
            self._recorder.record(RevertOutcome.of(location.id, change, ACTION_ALERT))
            return RevertResult(ACTION_ALERT, change.field)

        # action == ACTION_REVERT — bounded, rate-limited, gateway-checked.
        if not self._rate_limiter.allow(location.id):
            # Too many recent reverts: stop fighting the edit, fall back to alert.
            self._recorder.record(RevertOutcome.of(location.id, change, ACTION_ALERT))
            return RevertResult(ACTION_ALERT, change.field, rate_limited=True)

        baseline_value = self._baseline_value(location, change.field)
        self._restore(location, change.field, baseline_value)
        self._rate_limiter.record(location.id)
        self._recorder.record(RevertOutcome.of(location.id, change, ACTION_REVERT))
        return RevertResult(ACTION_REVERT, change.field)

    # --- human-confirmed entry point -------------------------------------

    def restore_field(self, *, location: Any, field: str) -> RevertResult:
        """One-click restore of ``field`` to its locked baseline (human-initiated).

        Works regardless of ``revert_mode`` — a person explicitly asked for it, so it
        is never a silent write — but still passes the Policy Gateway and is audited.
        No rate-limit gate: a manual action is not automation to throttle.
        """
        baseline_value = self._baseline_value(location, field)
        change = self._manual_change(location, field, baseline_value)
        self._restore(location, field, baseline_value)
        self._recorder.record(RevertOutcome.of(location.id, change, ACTION_REVERT))
        return RevertResult(ACTION_REVERT, field)

    # --- shared write path -----------------------------------------------

    def _restore(self, location: Any, field: str, value: Any) -> None:
        """Guard the restore through the Policy Engine, then write it. No bypass."""
        guarded = ExternalWrite(
            ACTION_LISTING_EDIT,
            metadata={"field": field, "value": value, "reason": "profile_protection_revert"},
        )
        # Mandatory: raises 422 and never returns on a hard violation, so the
        # writer below cannot run on a non-compliant write (CLAUDE.md hard rule).
        self._gateway.guard(guarded)
        self._writer.restore_field(location_id=location.id, field=field, value=value)

    @staticmethod
    def _baseline_value(location: Any, field: str) -> Any:
        baseline = location.profile_data_locked or {}
        if field not in baseline:
            raise BaselineUnavailableError(
                f"no locked baseline value for field {field!r} on location {location.id}"
            )
        return baseline[field]

    @staticmethod
    def _manual_change(location: Any, field: str, baseline_value: Any) -> ProfileChange:
        """Build the audit record for a manual restore (live → baseline)."""
        live = (location.profile_data_live or {}).get(field)
        # A manual restore of a critical field is recorded high; otherwise medium.
        severity = "high" if field in AUTO_REVERT_CRITICAL_FIELDS else "medium"
        return ProfileChange(
            field=field,
            old_value=baseline_value,
            new_value=live,
            severity=severity,
        )
