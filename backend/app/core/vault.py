"""Token vault interface — stub implementation for local development.

Production deployments wire this to HashiCorp Vault (or equivalent) via
VAULT_URL / VAULT_KV_PATH env vars. The stub keeps secrets in memory only
and is intentionally ephemeral — never persist or log these values.

COMPLIANCE: raw OAuth tokens must never be stored in Postgres. Call
vault.set_secret(value) and persist only the returned opaque token_ref
in the DB (see CLAUDE.md hard rules, P1D-1 for the real vault wiring).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class TokenVaultError(Exception):
    """Raised when a vault operation fails (missing ref, auth error, etc.)."""


class TokenVault:
    """Minimal interface all vault backends must satisfy.

    Only the opaque token_ref string crosses the application boundary to the DB.
    The raw secret is fetched from the vault on demand and never persisted.
    """

    async def get_secret(self, ref: str) -> str:
        """Fetch the secret value identified by ref."""
        raise NotImplementedError

    async def set_secret(self, ref: str, value: str) -> str:
        """Store value and return an opaque ref to be persisted in the DB."""
        raise NotImplementedError

    async def delete_secret(self, ref: str) -> None:
        """Permanently remove the secret identified by ref."""
        raise NotImplementedError


class LocalDevVault(TokenVault):
    """In-memory vault stub for local development and unit tests.

    Secrets survive only for the process lifetime. Never use in production.
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get_secret(self, ref: str) -> str:
        try:
            return self._store[ref]
        except KeyError:
            raise TokenVaultError(f"No secret found for ref: {ref!r}") from None

    async def set_secret(self, ref: str, value: str) -> str:
        self._store[ref] = value
        logger.debug("LocalDevVault: stored secret ref=%r", ref)
        return ref

    async def delete_secret(self, ref: str) -> None:
        self._store.pop(ref, None)


def get_vault() -> TokenVault:
    """Return the active vault implementation.

    Wire a real vault backend here in ticket P1D-1.
    """
    from app.core.config import settings  # local import — avoids circular at module load

    if settings.vault_url:
        raise NotImplementedError(
            "Production vault not yet implemented. Wire HashiCorpVault in P1D-1 "
            f"(VAULT_URL={settings.vault_url!r})."
        )
    return LocalDevVault()
