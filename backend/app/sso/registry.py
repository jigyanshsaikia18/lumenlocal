"""Provider registry — maps provider name to SsoProvider instance.

Swap MockSsoProvider entries for production SAML/OIDC implementations.
"""
from __future__ import annotations

from app.sso.base import SsoProvider
from app.sso.mock import MockSsoProvider

_PROVIDERS: dict[str, SsoProvider] = {
    "saml": MockSsoProvider(),
    "oidc": MockSsoProvider(),
}


def get_provider(name: str) -> SsoProvider | None:
    return _PROVIDERS.get(name)
