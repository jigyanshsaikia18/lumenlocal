"""The pure bounded-revert policy (P4A-2): which mode + change yields which action.

These prove the *decision* in isolation — no gateway, writer, or DB. The two load-
bearing guarantees: ``alert_only`` never decides to write, and ``auto_revert_critical``
decides to write **only** for a narrow critical-field set on a high-severity change.
"""
import pytest

from app.protection import (
    ACTION_ALERT,
    ACTION_NONE,
    ACTION_REVERT,
    REVERT_MODE_ALERT_ONLY,
    REVERT_MODE_AUTO_CRITICAL,
    REVERT_MODE_OFF,
    ProfileChange,
    decide,
    is_auto_revertible,
)
from app.protection.fields import (
    FIELD_DESCRIPTION,
    FIELD_HOURS,
    FIELD_LATITUDE,
    FIELD_NAME,
    FIELD_PHONE,
    FIELD_PRIMARY_CATEGORY,
    FIELD_WEBSITE,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
)

CRITICAL_FIELDS = [FIELD_NAME, FIELD_PRIMARY_CATEGORY, FIELD_PHONE, FIELD_LATITUDE]
NON_CRITICAL_FIELDS = [FIELD_DESCRIPTION, FIELD_HOURS, FIELD_WEBSITE]


def _change(field, severity=SEVERITY_HIGH):
    return ProfileChange(field=field, old_value="old", new_value="new", severity=severity)


# --- alert_only: never a revert -------------------------------------------------


@pytest.mark.parametrize("field", CRITICAL_FIELDS)
def test_alert_only_never_reverts_even_critical_high(field):
    assert decide(REVERT_MODE_ALERT_ONLY, _change(field, SEVERITY_HIGH)) == ACTION_ALERT


# --- auto_revert_critical: only allowed fields, only high severity --------------


@pytest.mark.parametrize("field", CRITICAL_FIELDS)
def test_auto_reverts_critical_field_on_high_severity(field):
    assert decide(REVERT_MODE_AUTO_CRITICAL, _change(field, SEVERITY_HIGH)) == ACTION_REVERT


@pytest.mark.parametrize("field", NON_CRITICAL_FIELDS)
def test_auto_does_not_revert_non_critical_field_even_high(field):
    # The core "only allowed fields" guarantee: a non-critical field is alert-only.
    assert decide(REVERT_MODE_AUTO_CRITICAL, _change(field, SEVERITY_HIGH)) == ACTION_ALERT


@pytest.mark.parametrize("severity", [SEVERITY_LOW, SEVERITY_MEDIUM])
def test_auto_does_not_revert_critical_field_below_high(severity):
    # A critical field changed ambiguously (low/medium) is too uncertain to write back.
    assert decide(REVERT_MODE_AUTO_CRITICAL, _change(FIELD_NAME, severity)) == ACTION_ALERT


# --- off: nothing ----------------------------------------------------------------


def test_off_does_nothing_even_for_malicious_critical_change():
    assert decide(REVERT_MODE_OFF, _change(FIELD_NAME, SEVERITY_HIGH)) == ACTION_NONE


# --- is_auto_revertible predicate -----------------------------------------------


def test_is_auto_revertible_requires_both_critical_field_and_high():
    assert is_auto_revertible(_change(FIELD_NAME, SEVERITY_HIGH)) is True
    assert is_auto_revertible(_change(FIELD_NAME, SEVERITY_MEDIUM)) is False
    assert is_auto_revertible(_change(FIELD_DESCRIPTION, SEVERITY_HIGH)) is False


# --- validation ------------------------------------------------------------------


def test_decide_rejects_unknown_mode():
    with pytest.raises(ValueError):
        decide("auto_revert_everything", _change(FIELD_NAME))


def test_profile_change_rejects_unknown_severity():
    with pytest.raises(ValueError):
        ProfileChange(field=FIELD_NAME, old_value="a", new_value="b", severity="catastrophic")
