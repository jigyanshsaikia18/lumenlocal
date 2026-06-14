"""The unit the revert policy evaluates: one detected profile change (P4A-2).

A :class:`ProfileChange` is the in-code mirror of a ``profile_change_events`` row
(schema §7): which monitored ``field`` moved, its ``old_value`` (from the locked
baseline ``profile_data_locked``) and ``new_value`` (the live value detected on
Google), and the ``severity`` the monitor assigned.

Keeping the policy's input this small deliberately decouples P4A-2 from P4A-1's
not-yet-built detection worker: the worker constructs ``ProfileChange`` objects and
hands them to :class:`app.protection.service.ProtectionService`; the pure decision
in :mod:`app.protection.revert` never needs the worker, a DB, or the Google API.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.protection.fields import SEVERITY_HIGH, SEVERITY_LOW, SEVERITY_MEDIUM

_VALID_SEVERITIES = frozenset({SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH})


@dataclass(frozen=True)
class ProfileChange:
    """A single detected change to one monitored field.

    Frozen so a change cannot be mutated between the policy decision and the
    corrective write it authorises.
    """

    field: str
    old_value: Any
    new_value: Any
    severity: str

    def __post_init__(self) -> None:
        if self.severity not in _VALID_SEVERITIES:
            raise ValueError(
                f"unknown severity {self.severity!r}; "
                f"expected one of {sorted(_VALID_SEVERITIES)}"
            )
