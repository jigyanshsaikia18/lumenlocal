"""Monitored profile fields + criticality (profile protection, PRD §7 / Module 7).

Protection watches 20+ profile fields for unauthorized change. Only a *narrow*
subset is ever eligible for an automated corrective write, and only then under the
``auto_revert_critical`` mode on an unambiguous high-severity change — CLAUDE.md is
explicit: do NOT build unsupervised corrective writes to critical fields
(name / category / phone / pin). This module is the single source of truth for
"which fields", "which are auto-revertible", and the severity vocabulary the policy
in :mod:`app.protection.revert` reads.

Severity classification itself (e.g. *how far* a pin must move to count as high) is
the monitor's job (P4A-1); :func:`pin_move_is_critical` is provided so that worker —
and our own tests — share one threshold rather than re-deriving it.
"""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

# --- Monitored field keys (subset of the 20+; names match profile_data_* JSONB) --
FIELD_NAME = "name"
FIELD_PRIMARY_CATEGORY = "primary_category"
FIELD_PHONE = "phone"
FIELD_LATITUDE = "latitude"
FIELD_LONGITUDE = "longitude"
# Non-critical monitored fields — alerted on change, never auto-reverted.
FIELD_DESCRIPTION = "description"
FIELD_HOURS = "hours"
FIELD_WEBSITE = "website"
FIELD_ATTRIBUTES = "attributes"

#: Fields eligible for a *bounded* auto-revert (CLAUDE.md "name/category/phone/pin").
#: The map pin is the (latitude, longitude) pair. Membership here is half of the
#: structural guarantee that auto-revert can only ever touch allowed fields — see
#: :func:`app.protection.revert.is_auto_revertible`. Any field NOT in this set is
#: alert-only forever, regardless of mode or severity.
AUTO_REVERT_CRITICAL_FIELDS = frozenset(
    {
        FIELD_NAME,
        FIELD_PRIMARY_CATEGORY,
        FIELD_PHONE,
        FIELD_LATITUDE,
        FIELD_LONGITUDE,
    }
)

# --- Severity vocabulary (mirrors profile_change_events.severity, schema §7) ------
SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"

#: A map-pin move farther than this is unambiguously high-risk (a moved pin sends
#: customers to the wrong place — a documented hijack pattern). Used by the monitor
#: to classify pin severity; kept here so the threshold lives in exactly one place.
PIN_MOVE_THRESHOLD_METERS = 50.0

_EARTH_RADIUS_METERS = 6_371_000.0


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in metres."""
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_METERS * asin(sqrt(a))


def pin_move_is_critical(
    old: tuple[float, float] | None, new: tuple[float, float] | None
) -> bool:
    """True if the pin moved beyond :data:`PIN_MOVE_THRESHOLD_METERS`.

    A missing endpoint (pin set or cleared) counts as critical — appearing or
    vanishing coordinates are as disruptive as a large move.
    """
    if old is None or new is None:
        return old != new
    return haversine_meters(old[0], old[1], new[0], new[1]) > PIN_MOVE_THRESHOLD_METERS
