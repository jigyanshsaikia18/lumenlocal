"""Mock/stub SSO provider for development and tests (P1B-3).

Treats the raw token value as the sso_subject — no external call.
Replace with real SAML assertion / OIDC id_token validation in production.
"""
from __future__ import annotations

from app.sso.base import SsoProvider


class MockSsoProvider(SsoProvider):
    def exchange(self, token: str) -> str | None:
        return token or None
