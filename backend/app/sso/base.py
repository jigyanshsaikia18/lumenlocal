"""Abstract hook point for SAML/OIDC identity providers (P1B-3 scaffold).

In production, swap MockSsoProvider for a library that validates the token
against the tenant's configured issuer (e.g. python-saml, authlib).
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class SsoProvider(ABC):
    """Validates a raw SSO token and returns the canonical sso_subject string.

    Returns None when the token is invalid or unrecognised.
    """

    @abstractmethod
    def exchange(self, token: str) -> str | None: ...
