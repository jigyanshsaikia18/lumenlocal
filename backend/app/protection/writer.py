"""The seam to the actual Google profile write (P4A-2).

A revert restores one baseline field value on the live Google Business Profile —
an *external write*, so it must pass the Policy Compliance Gateway first and may
only happen through :class:`app.protection.service.ProtectionService`. This module
defines just the boundary: :class:`ProfileWriter`. The real GBP-API implementation
is out of scope for this ticket (it lands with the connection/write plumbing); the
point here is that the service depends on this Protocol, never on a concrete client,
so the suite can inject a spy and assert the writer is **never** called in
``alert_only`` / ``off`` and is called with the baseline value (only) on a revert.
"""
from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID


class ProfileWriter(Protocol):
    """Performs the actual restore of one field on the live Google profile.

    Called by the service **only after** ``PolicyGateway.guard`` has passed, never
    directly by a handler or worker — that is what keeps every outbound write on the
    sanctioned, policy-checked path.
    """

    def restore_field(self, *, location_id: UUID, field: str, value: Any) -> None:
        """Write ``value`` back to ``field`` on ``location_id``'s Google profile."""
        ...
