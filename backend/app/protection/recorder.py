"""Recording protection outcomes to the audit trail (P4A-2, schema §7).

Every decision the service makes — an alert, a revert, an ignored change — is
appended to ``profile_change_events`` with its ``action_taken``. That table is the
protection audit trail: the proof that a critical change was caught and what the
platform did about it (PRD §7). ``RevertOutcome`` is the in-code row; the recorder
is an injectable seam (Protocol) with an in-memory implementation for tests and a
SQLAlchemy one that appends to the table. The platform-wide ``audit_log`` (P1E-3)
can subscribe through this same seam later; here the protection trail is enough.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.protection.changes import ProfileChange


@dataclass(frozen=True)
class RevertOutcome:
    """One ``profile_change_events`` row: what changed and what we did about it."""

    location_id: UUID
    field: str
    old_value: Any
    new_value: Any
    severity: str
    action_taken: str  # alerted / reverted / ignored (mirrors revert.ACTION_*)

    @classmethod
    def of(
        cls, location_id: UUID, change: ProfileChange, action_taken: str
    ) -> "RevertOutcome":
        """Build an outcome from a detected change plus the action taken on it."""
        return cls(
            location_id=location_id,
            field=change.field,
            old_value=change.old_value,
            new_value=change.new_value,
            severity=change.severity,
            action_taken=action_taken,
        )


class ChangeEventRecorder(Protocol):
    """Appends protection outcomes to the audit trail."""

    def record(self, outcome: RevertOutcome) -> None: ...


class InMemoryChangeEventRecorder:
    """Collects outcomes in a list (tests / dry runs)."""

    def __init__(self) -> None:
        self.outcomes: list[RevertOutcome] = []

    def record(self, outcome: RevertOutcome) -> None:
        self.outcomes.append(outcome)


class SqlAlchemyChangeEventRecorder:
    """Append outcomes to ``profile_change_events``.

    Runs as the ``lumen_app`` role (granted SELECT/INSERT only — the trail is
    append-only); RLS constrains rows to the request's tenant transitively through
    ``location_id``. The caller owns the surrounding transaction/commit, as
    elsewhere in the app (cf. ``SqlAlchemyComplianceEventSink``).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, outcome: RevertOutcome) -> None:
        self._session.execute(
            text(
                "INSERT INTO profile_change_events "
                "(location_id, field, old_value, new_value, severity, action_taken) "
                "VALUES (:location_id, :field, CAST(:old_value AS jsonb), "
                "CAST(:new_value AS jsonb), :severity, :action_taken)"
            ),
            {
                "location_id": outcome.location_id,
                "field": outcome.field,
                "old_value": json.dumps(outcome.old_value),
                "new_value": json.dumps(outcome.new_value),
                "severity": outcome.severity,
                "action_taken": outcome.action_taken,
            },
        )
