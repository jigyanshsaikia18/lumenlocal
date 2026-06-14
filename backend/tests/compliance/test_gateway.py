"""The mandatory gateway (P3A-2): a blocked write raises 422 with
``{rule, ruleset_version}`` AND is logged to compliance_events *before* the raise,
while a passing write returns its decision so the caller may proceed.

Uses an in-memory event sink so the gateway is exercised end-to-end without a DB
(the SQLAlchemy sink is integration-tested where Postgres is available).
"""
from uuid import uuid4

import pytest

from app.compliance import (
    ACTION_REVIEW_REPLY,
    ACTION_REVIEW_REQUEST,
    ComplianceEventData,
    DEFAULT_RULESET,
    ExternalWrite,
    PolicyComplianceEngine,
    PolicyGateway,
    RULE_INCENTIVE,
)
from app.core.errors import APIError


class _MemorySink:
    """In-memory ComplianceEventSink for tests."""

    def __init__(self) -> None:
        self.events: list[ComplianceEventData] = []

    def record(self, event: ComplianceEventData) -> None:
        self.events.append(event)


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def sink():
    return _MemorySink()


@pytest.fixture
def gateway(sink, tenant_id):
    engine = PolicyComplianceEngine(DEFAULT_RULESET)
    return PolicyGateway(engine, sink, tenant_id=tenant_id)


def test_blocked_write_raises_422_with_rule_and_version(gateway):
    with pytest.raises(APIError) as exc_info:
        gateway.guard(
            ExternalWrite(ACTION_REVIEW_REPLY, content="Here's a discount for your review!")
        )
    err = exc_info.value
    assert err.status_code == 422
    assert err.code == "policy_violation"
    assert err.details == {
        "rule": RULE_INCENTIVE,
        "ruleset_version": DEFAULT_RULESET.version,
    }


def test_blocked_write_is_logged_to_compliance_events(gateway, sink, tenant_id):
    with pytest.raises(APIError):
        gateway.guard(
            ExternalWrite(ACTION_REVIEW_REQUEST, content="Free gift for every review!")
        )
    assert len(sink.events) == 1
    event = sink.events[0]
    assert event.tenant_id == tenant_id
    assert event.action_type == ACTION_REVIEW_REQUEST
    assert event.outcome == "blocked"
    assert event.rule_violated == RULE_INCENTIVE
    assert event.ruleset_version == DEFAULT_RULESET.version


def test_passing_write_returns_decision_and_logs_nothing(gateway, sink):
    decision = gateway.guard(
        ExternalWrite(ACTION_REVIEW_REPLY, content="Thanks for the lovely review!")
    )
    assert decision.passed
    assert sink.events == []
