"""In-memory refresh-token revocation store (Phase 1).

Process-local — does not survive restarts or work across multiple workers.
Replace with Redis (DB 2, dedicated key namespace) when the queue layer
is built in Phase 2.
"""
from __future__ import annotations

_revoked: set[str] = set()


def revoke(jti: str) -> None:
    _revoked.add(jti)


def is_revoked(jti: str) -> bool:
    return jti in _revoked


def clear_all() -> None:
    """Test helper: reset between test runs."""
    _revoked.clear()
