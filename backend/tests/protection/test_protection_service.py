"""The protection executor end-to-end (P4A-2), with a spy writer + real gateway.

The two acceptance proofs the ticket calls out:

* ``alert_only`` (and ``off``) **never** write to Google — the spy writer is never
  called and the Policy Gateway is never even consulted.
* ``auto_revert_critical`` reverts **only** allowed critical fields — and when it
  does, the write goes through the Policy Gateway first, restores the locked
  baseline value, is rate-limited, and is audited.
"""
import dataclasses

import pytest

from app.compliance import DEFAULT_RULESET, PolicyComplianceEngine, PolicyGateway
from app.core.errors import APIError
from app.protection import (
    ACTION_ALERT,
    ACTION_NONE,
    ACTION_REVERT,
    REVERT_MODE_ALERT_ONLY,
    REVERT_MODE_AUTO_CRITICAL,
    REVERT_MODE_OFF,
    BaselineUnavailableError,
    ProfileChange,
    ProtectionService,
)
from app.protection.fields import FIELD_DESCRIPTION, FIELD_NAME, SEVERITY_HIGH

from .conftest import SpyGateway, make_location


def _name_change():
    return ProfileChange(
        field=FIELD_NAME, old_value="Joe's Pizza", new_value="Joe's Pizza CLOSED", severity=SEVERITY_HIGH
    )


# --- alert_only: the headline guarantee — never writes ---------------------------


def test_alert_only_never_writes_to_google(service, writer, gateway, recorder):
    loc = make_location(revert_mode=REVERT_MODE_ALERT_ONLY, locked={FIELD_NAME: "Joe's Pizza"})

    result = service.process_change(location=loc, change=_name_change())

    assert result.action == ACTION_ALERT
    assert writer.calls == []  # nothing was written to Google
    assert gateway.guard_calls == []  # the gateway was not even consulted
    # …but the change was recorded as an alert (audit trail).
    assert len(recorder.outcomes) == 1
    assert recorder.outcomes[0].action_taken == ACTION_ALERT
    assert recorder.outcomes[0].field == FIELD_NAME


# --- off: nothing at all ---------------------------------------------------------


def test_off_writes_nothing_and_records_nothing(service, writer, gateway, recorder):
    loc = make_location(revert_mode=REVERT_MODE_OFF, locked={FIELD_NAME: "Joe's Pizza"})

    result = service.process_change(location=loc, change=_name_change())

    assert result.action == ACTION_NONE
    assert writer.calls == []
    assert gateway.guard_calls == []
    assert recorder.outcomes == []


# --- auto_revert_critical: reverts only allowed fields ---------------------------


def test_auto_revert_critical_field_writes_baseline_through_gateway(
    service, writer, gateway, recorder
):
    loc = make_location(
        revert_mode=REVERT_MODE_AUTO_CRITICAL, locked={FIELD_NAME: "Joe's Pizza"}
    )

    result = service.process_change(location=loc, change=_name_change())

    assert result.action == ACTION_REVERT
    # The write went through the Policy Gateway first, then to Google exactly once.
    assert len(gateway.guard_calls) == 1
    assert len(writer.calls) == 1
    call = writer.calls[0]
    assert call["location_id"] == loc.id
    assert call["field"] == FIELD_NAME
    assert call["value"] == "Joe's Pizza"  # the locked baseline, not the live value
    # Audited as a revert.
    assert recorder.outcomes[-1].action_taken == ACTION_REVERT


def test_auto_revert_skips_non_critical_field(service, writer, gateway, recorder):
    loc = make_location(
        revert_mode=REVERT_MODE_AUTO_CRITICAL, locked={FIELD_DESCRIPTION: "We sell pizza."}
    )
    change = ProfileChange(
        field=FIELD_DESCRIPTION, old_value="We sell pizza.", new_value="spam", severity=SEVERITY_HIGH
    )

    result = service.process_change(location=loc, change=change)

    # A non-critical field is never auto-written, even at high severity.
    assert result.action == ACTION_ALERT
    assert writer.calls == []
    assert gateway.guard_calls == []
    assert recorder.outcomes[-1].action_taken == ACTION_ALERT


# --- fail-closed: a revert that the gateway blocks never reaches Google ----------


def test_revert_blocked_by_gateway_does_not_write(writer, rate_limiter, recorder, tenant_id):
    # A ruleset under which the revert's listing-edit metadata trips a hard rule, so
    # guard() raises 422. Proves the writer is downstream of the gateway: fail-closed.
    blocking_ruleset = dataclasses.replace(DEFAULT_RULESET, gating_fields=("field",))
    inner = PolicyGateway(
        PolicyComplianceEngine(blocking_ruleset), _NullSink(), tenant_id=tenant_id
    )
    gateway = SpyGateway(inner)
    service = ProtectionService(
        gateway=gateway, writer=writer, rate_limiter=rate_limiter, recorder=recorder
    )
    loc = make_location(revert_mode=REVERT_MODE_AUTO_CRITICAL, locked={FIELD_NAME: "Joe's Pizza"})

    with pytest.raises(APIError) as exc:
        service.process_change(location=loc, change=_name_change())

    assert exc.value.status_code == 422
    assert gateway.guard_calls  # the gateway was consulted…
    assert writer.calls == []  # …and blocked, so Google was never written
    # Not recorded as a successful revert.
    assert all(o.action_taken != ACTION_REVERT for o in recorder.outcomes)


class _NullSink:
    def record(self, event) -> None:  # noqa: D401, ANN001
        pass


# --- rate limiting: a flapping field falls back to alert -------------------------


def test_auto_revert_is_rate_limited(gateway, writer, recorder, tenant_id):
    from app.protection import InMemoryRevertRateLimiter

    limiter = InMemoryRevertRateLimiter(max_reverts=2, window_seconds=3600)
    service = ProtectionService(
        gateway=gateway, writer=writer, rate_limiter=limiter, recorder=recorder
    )
    loc = make_location(revert_mode=REVERT_MODE_AUTO_CRITICAL, locked={FIELD_NAME: "Joe's Pizza"})

    r1 = service.process_change(location=loc, change=_name_change())
    r2 = service.process_change(location=loc, change=_name_change())
    r3 = service.process_change(location=loc, change=_name_change())

    assert (r1.action, r2.action) == (ACTION_REVERT, ACTION_REVERT)
    assert len(writer.calls) == 2  # only the first two actually wrote
    # The third is over the cap: downgraded to an alert, not written.
    assert r3.action == ACTION_ALERT
    assert r3.rate_limited is True
    assert len(writer.calls) == 2


# --- baseline guard --------------------------------------------------------------


def test_revert_without_baseline_value_does_not_write(service, writer):
    loc = make_location(revert_mode=REVERT_MODE_AUTO_CRITICAL, locked={})  # no baseline name

    with pytest.raises(BaselineUnavailableError):
        service.process_change(location=loc, change=_name_change())

    assert writer.calls == []


# --- one-click restore: human-confirmed, works in any mode -----------------------


def test_one_click_restore_writes_through_gateway_even_in_alert_only(
    service, writer, gateway, recorder
):
    loc = make_location(
        revert_mode=REVERT_MODE_ALERT_ONLY,
        locked={FIELD_NAME: "Joe's Pizza"},
        live={FIELD_NAME: "Joe's Pizza CLOSED"},
    )

    result = service.restore_field(location=loc, field=FIELD_NAME)

    # A person asked for it — so it writes, even though auto-revert is off — but
    # still through the Policy Gateway and into the audit trail.
    assert result.action == ACTION_REVERT
    assert len(gateway.guard_calls) == 1
    assert writer.calls[0]["value"] == "Joe's Pizza"
    assert recorder.outcomes[-1].action_taken == ACTION_REVERT
