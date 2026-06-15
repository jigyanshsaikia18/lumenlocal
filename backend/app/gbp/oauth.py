"""Google OAuth + GBP location client (P1D-1).

Three operations the connect flow needs from Google, behind one abstract class so
tests inject a mock:

* :meth:`GbpOAuthClient.consent_url` — the URL the operator sends the client to.
* :meth:`GbpOAuthClient.exchange_code` — swap the redirect ``code`` for tokens.
* :meth:`GbpOAuthClient.list_locations` — pull the locations the token manages.

:class:`OAuthToken` is the *raw secret* that must only ever reach the vault — it is
serialised to a string for ``vault.set_secret`` and never persisted to Postgres
(CLAUDE.md hard rule). :class:`RemoteLocation` is the non-secret shape imported
into the ``locations`` table.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

# The single scope the platform requests; raw tokens carrying it are vaulted, not
# stored (see config.py). Keep aligned with the Google Cloud Console consent screen.
GBP_SCOPES: tuple[str, ...] = ("https://www.googleapis.com/auth/business.manage",)
GOOGLE_AUTHORIZE_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"


@dataclass
class OAuthToken:
    """The raw Google token bundle — VAULT ONLY, never persisted to the DB."""

    access_token: str
    refresh_token: str | None
    scopes: list[str] = field(default_factory=list)
    expires_at: datetime | None = None

    def serialize(self) -> str:
        """JSON string for ``vault.set_secret`` (the only place this may be stored)."""
        return json.dumps(
            {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "scopes": self.scopes,
                "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            }
        )

    @classmethod
    def deserialize(cls, raw: str) -> OAuthToken:
        data = json.loads(raw)
        expires = data.get("expires_at")
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            scopes=list(data.get("scopes") or []),
            expires_at=datetime.fromisoformat(expires) if expires else None,
        )


@dataclass
class RemoteLocation:
    """One GBP location as returned by Google (non-secret; safe to persist)."""

    google_place_id: str
    latitude: float | None = None
    longitude: float | None = None
    profile_data: dict = field(default_factory=dict)


class GbpOAuthClient(ABC):
    """Abstract Google OAuth + GBP client (mock this in tests)."""

    @abstractmethod
    def consent_url(self, state: str) -> str: ...

    @abstractmethod
    async def exchange_code(self, code: str) -> OAuthToken: ...

    @abstractmethod
    async def list_locations(self, token: OAuthToken) -> list[RemoteLocation]: ...


class GoogleGbpOAuthClient(GbpOAuthClient):
    """Real client. Builds the consent URL from configured credentials.

    The token-exchange and location-list HTTP calls are wired against the live
    Google APIs in a later ticket (P1D-2); until then they fail loudly rather than
    silently returning fake data.
    """

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri

    def consent_url(self, state: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": " ".join(GBP_SCOPES),
            "state": state,
            # offline + consent so Google returns a refresh_token we can vault.
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
        return f"{GOOGLE_AUTHORIZE_ENDPOINT}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> OAuthToken:  # pragma: no cover - real HTTP, P1D-2
        raise NotImplementedError(
            "Live Google token exchange is wired in P1D-2; configure the mock for local dev."
        )

    async def list_locations(self, token: OAuthToken) -> list[RemoteLocation]:  # pragma: no cover
        raise NotImplementedError(
            "Live GBP location listing is wired in P1D-2; configure the mock for local dev."
        )


class MockGbpOAuthClient(GbpOAuthClient):
    """Deterministic in-memory client for local dev and unit tests.

    Returns a fixed token bundle and two locations so the connect → vault → import
    path is fully exercisable without the network. The tokens are obvious fakes so
    they can never be mistaken for real secrets.
    """

    def consent_url(self, state: str) -> str:
        return f"https://mock.google/o/oauth2/consent?{urlencode({'state': state})}"

    async def exchange_code(self, code: str) -> OAuthToken:
        return OAuthToken(
            access_token=f"mock-access-token-for-{code}",
            refresh_token="mock-refresh-token",
            scopes=list(GBP_SCOPES),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

    async def list_locations(self, token: OAuthToken) -> list[RemoteLocation]:
        return [
            RemoteLocation(
                google_place_id="mock-place-aurora-cafe",
                latitude=37.422,
                longitude=-122.084,
                profile_data={"name": "Aurora Cafe", "primary_category": "Cafe"},
            ),
            RemoteLocation(
                google_place_id="mock-place-aurora-roastery",
                latitude=37.776,
                longitude=-122.417,
                profile_data={"name": "Aurora Roastery", "primary_category": "Coffee shop"},
            ),
        ]


def get_gbp_client() -> GbpOAuthClient:
    """Return the active GBP client — real when credentials are set, else the mock."""
    from app.core.config import settings  # local import avoids a config import cycle

    if settings.google_oauth_client_id and settings.google_oauth_client_secret:
        return GoogleGbpOAuthClient(
            settings.google_oauth_client_id,
            settings.google_oauth_client_secret,
            settings.google_oauth_redirect_uri,
        )
    return MockGbpOAuthClient()
