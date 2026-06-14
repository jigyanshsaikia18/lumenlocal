"""P0-3 acceptance: settings loader and token vault stub.

Tests in this module construct Settings() directly (not via the module-level
cached `settings` singleton) so they can exercise error paths without affecting
other tests.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


# ── Settings loader ───────────────────────────────────────────────────────────

def test_settings_loads_when_required_vars_present():
    """Settings constructs successfully when SECRET_KEY is provided."""
    s = Settings(secret_key="a-valid-test-key", _env_file=None)
    assert s.secret_key.get_secret_value() == "a-valid-test-key"
    assert s.environment == "development"
    assert s.app_name == "LumenLocal"


def test_settings_fails_clearly_when_secret_key_missing(monkeypatch):
    """Startup must raise ValidationError — not hang or produce a silent default —
    when SECRET_KEY is absent from both the environment and .env files."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)
    # The error must name the missing field so operators know exactly what to fix.
    assert "secret_key" in str(exc_info.value).lower()


def test_secret_key_masked_in_repr():
    """SecretStr must hide the raw value in repr/str to prevent accidental logging."""
    s = Settings(secret_key="super-secret-value", _env_file=None)
    assert "super-secret-value" not in repr(s)
    assert "super-secret-value" not in str(s)


def test_get_settings_returns_same_instance():
    """The lru_cache must return the same Settings object on repeated calls."""
    assert get_settings() is get_settings()


def test_database_url_has_sane_default():
    s = Settings(secret_key="x", _env_file=None)
    assert s.database_url.startswith("postgresql+psycopg://")
    assert s.app_database_url.startswith("postgresql+psycopg://")


def test_redis_url_has_sane_default():
    s = Settings(secret_key="x", _env_file=None)
    assert s.redis_url.startswith("redis://")
    assert s.celery_broker_url.startswith("redis://")


def test_google_oauth_defaults_are_empty():
    """Google OAuth vars must default to empty — never a real credential placeholder."""
    s = Settings(secret_key="x", _env_file=None)
    assert s.google_oauth_client_id == ""
    assert s.google_oauth_client_secret == ""


def test_vault_url_defaults_to_empty():
    """Empty VAULT_URL means LocalDevVault stub is used (see app/core/vault.py)."""
    s = Settings(secret_key="x", _env_file=None)
    assert s.vault_url == ""


# ── Token vault stub ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_local_dev_vault_roundtrip():
    from app.core.vault import LocalDevVault

    vault = LocalDevVault()
    ref = await vault.set_secret("oauth:tenant:abc123", "tok_test_value_xyz")
    assert ref == "oauth:tenant:abc123"
    assert await vault.get_secret(ref) == "tok_test_value_xyz"


@pytest.mark.asyncio
async def test_local_dev_vault_missing_ref_raises():
    from app.core.vault import LocalDevVault, TokenVaultError

    vault = LocalDevVault()
    with pytest.raises(TokenVaultError, match="nonexistent-ref"):
        await vault.get_secret("nonexistent-ref")


@pytest.mark.asyncio
async def test_local_dev_vault_delete_removes_secret():
    from app.core.vault import LocalDevVault, TokenVaultError

    vault = LocalDevVault()
    await vault.set_secret("ref-to-delete", "some-token")
    await vault.delete_secret("ref-to-delete")
    with pytest.raises(TokenVaultError):
        await vault.get_secret("ref-to-delete")


@pytest.mark.asyncio
async def test_local_dev_vault_delete_nonexistent_is_silent():
    """Deleting a ref that was never stored must not raise."""
    from app.core.vault import LocalDevVault

    vault = LocalDevVault()
    await vault.delete_secret("ref-that-was-never-set")  # should not raise


@pytest.mark.asyncio
async def test_local_dev_vault_secrets_are_isolated():
    """Each LocalDevVault instance has its own store — no cross-instance leakage."""
    from app.core.vault import LocalDevVault

    v1 = LocalDevVault()
    v2 = LocalDevVault()
    await v1.set_secret("shared-ref", "value-in-v1")
    from app.core.vault import TokenVaultError

    with pytest.raises(TokenVaultError):
        await v2.get_secret("shared-ref")


def test_get_vault_returns_local_dev_vault_when_no_vault_url(monkeypatch):
    """With VAULT_URL unset, get_vault() must return the LocalDevVault stub."""
    from app.core import vault as vault_module
    from app.core.vault import LocalDevVault, get_vault

    monkeypatch.setattr(vault_module, "get_vault", get_vault)
    result = get_vault()
    assert isinstance(result, LocalDevVault)


def test_get_vault_raises_not_implemented_when_vault_url_set(monkeypatch):
    """With a VAULT_URL configured, get_vault() must refuse until P1D-1 wires it."""
    from app.core.config import settings
    from app.core.vault import get_vault

    monkeypatch.setattr(settings, "vault_url", "https://vault.example.com")
    with pytest.raises(NotImplementedError, match="P1D-1"):
        get_vault()
