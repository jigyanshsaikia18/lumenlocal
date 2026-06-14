"""The mandatory compliance gateway — the single sanctioned path to an external write.

P3A-2's contract: *every* external write to Google passes the Policy Compliance
Engine; hard violations are **blocked with 422** carrying ``{rule, ruleset_version}``
and logged to ``compliance_events``; no module may bypass it (PRD §9, API spec §1,
CLAUDE.md hard rules).

This module is that chokepoint. A write handler does not call the provider API
directly — it builds an :class:`~app.compliance.actions.ExternalWrite` and calls
:meth:`PolicyGateway.guard`. ``guard`` either returns a passing
:class:`~app.compliance.engine.PolicyDecision` (the caller may then perform the
write) or raises :class:`~app.core.errors.APIError` ``422`` and never returns —
so an un-evaluated write cannot proceed. Every block is recorded via a
:class:`ComplianceEventSink` first.

The engine (decision) is pure; this layer adds exactly two side effects — the
event log and the ``422`` — and keeps them injectable so the gateway is testable
without a database (mirrors how ``app.entitlements`` splits resolver from store).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.compliance.actions import ExternalWrite
from app.compliance.engine import (
    OUTCOME_BLOCKED,
    PolicyComplianceEngine,
    PolicyDecision,
)
from app.compliance.rulesets import DEFAULT_RULESET, Ruleset
from app.core.errors import APIError


@dataclass(frozen=True)
class ComplianceEventData:
    """One row to append to ``compliance_events`` (schema §7)."""

    tenant_id: UUID
    action_type: str
    outcome: str
    rule_violated: str | None
    ruleset_version: int


class ComplianceEventSink(Protocol):
    """Where the gateway records compliance events (mock this in tests)."""

    def record(self, event: ComplianceEventData) -> None: ...


class PolicyGateway:
    """Guard external writes: evaluate, log violations, block with 422.

    ``tenant_id`` scopes the events written for this request. The ``engine`` is
    built from the active ruleset; ``sink`` persists events.
    """

    def __init__(
        self,
        engine: PolicyComplianceEngine,
        sink: ComplianceEventSink,
        *,
        tenant_id: UUID,
    ) -> None:
        self._engine = engine
        self._sink = sink
        self._tenant_id = tenant_id

    def guard(self, action: ExternalWrite) -> PolicyDecision:
        """Evaluate ``action``; on a hard violation log it and raise ``422``.

        Returns the passing decision so the caller may proceed with the write.
        Raises :class:`APIError` (422 ``policy_violation``) with
        ``details = {rule, ruleset_version}`` when blocked — and records the event
        *before* raising, so the proof trail exists even though the write never
        happened.
        """
        decision = self._engine.evaluate(action)
        if decision.blocked:
            self._sink.record(
                ComplianceEventData(
                    tenant_id=self._tenant_id,
                    action_type=action.action_type,
                    outcome=OUTCOME_BLOCKED,
                    rule_violated=decision.primary_rule,
                    ruleset_version=decision.ruleset_version,
                )
            )
            raise self._violation(action, decision)
        return decision

    @staticmethod
    def _violation(action: ExternalWrite, decision: PolicyDecision) -> APIError:
        message = (
            decision.violations[0].message
            if decision.violations
            else f"{action.action_type} blocked by policy."
        )
        return APIError(
            422,
            "policy_violation",
            message,
            {"rule": decision.primary_rule, "ruleset_version": decision.ruleset_version},
        )


# --- persistence seams ---------------------------------------------------


class SqlAlchemyComplianceEventSink:
    """Append compliance events to the ``compliance_events`` table.

    Runs as the ``lumen_app`` role (granted SELECT/INSERT by the migration); RLS
    constrains rows to the request's tenant. The caller is responsible for the
    surrounding transaction/commit, as elsewhere in the app.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, event: ComplianceEventData) -> None:
        self._session.execute(
            text(
                "INSERT INTO compliance_events "
                "(tenant_id, action_type, outcome, rule_violated, ruleset_version) "
                "VALUES (:tenant_id, :action_type, :outcome, :rule_violated, :ruleset_version)"
            ),
            {
                "tenant_id": event.tenant_id,
                "action_type": event.action_type,
                "outcome": event.outcome,
                "rule_violated": event.rule_violated,
                "ruleset_version": event.ruleset_version,
            },
        )


def load_active_ruleset(session: Session) -> Ruleset:
    """Load the active Policy Center ruleset, falling back to the built-in default.

    Reads the single ``is_active`` ``policy_rulesets`` row (highest version wins if
    more than one is somehow active) and rebuilds the typed :class:`Ruleset`. If
    none is present the built-in :data:`DEFAULT_RULESET` is used so the gateway is
    never silently disabled — fail *closed* on guardrails.
    """
    row = session.execute(
        text(
            "SELECT version, rules FROM policy_rulesets "
            "WHERE is_active = true ORDER BY version DESC LIMIT 1"
        )
    ).first()
    if row is None:
        return DEFAULT_RULESET
    return Ruleset.from_rules(row.version, row.rules)


def build_gateway(session: Session, *, tenant_id: UUID) -> PolicyGateway:
    """Compose a production gateway from a DB session + the request's tenant."""
    engine = PolicyComplianceEngine(load_active_ruleset(session))
    sink = SqlAlchemyComplianceEventSink(session)
    return PolicyGateway(engine, sink, tenant_id=tenant_id)
