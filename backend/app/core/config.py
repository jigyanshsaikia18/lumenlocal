"""Application settings — loaded from environment variables or .env files.

All settings are read at startup via pydantic-settings. Fields with no default
are REQUIRED; startup fails with a clear ValidationError if they are absent.

See .env.example at the repo root for the full list of variables and their
documentation. Copy it to .env (git-ignored) for local development.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = "LumenLocal"
    environment: str = "development"
    debug: bool = False
    frontend_url: str = "http://localhost:3000"
    # JSON array of origins that may send cross-origin requests to the API.
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # REQUIRED — JWT signing key. Generate with: openssl rand -hex 32
    # Startup raises ValidationError if SECRET_KEY is not set. Never commit a real value.
    secret_key: SecretStr

    # ── Auth / JWT ────────────────────────────────────────────────────────────
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # ── Entitlements (the toggle engine) ──────────────────────────────────────
    # How long the API gateway caches a client's resolved feature set before
    # re-reading the override tables. A toggle change therefore takes effect within
    # this window without a deploy (PRD §5 FT-2: "effect in < 1 minute"). Keep it
    # short; the override tables are cheap to read. The writer also invalidates the
    # local cache on change for instant effect on the node that served the toggle.
    entitlement_cache_ttl_seconds: int = 30

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    # Privileged connection: migrations, admin, health. Owns the schema and (in dev)
    # is a superuser, so it BYPASSES row-level security. Never use it for request handling.
    database_url: str = "postgresql+psycopg://lumen:lumen_dev_password@localhost:5432/lumenlocal"

    # Application connection: a non-superuser role that IS subject to row-level security.
    # Every tenant-scoped runtime query goes through this role (see app.db.session).
    app_database_url: str = (
        "postgresql+psycopg://lumen_app:lumen_app_dev_password@localhost:5432/lumenlocal"
    )

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── Job / Queue ───────────────────────────────────────────────────────────
    # Where ordinary tenant work lands. Heavy scan/sampling pools subscribe to
    # their own queues in later phases; this is the catch-all.
    jobs_default_queue: str = "default"
    # Retry policy for the TenantTask base. Exponential backoff with jitter is
    # applied on top (see app/jobs/base.py); this caps the number of attempts and
    # the longest backoff window.
    jobs_max_retries: int = 3
    jobs_retry_backoff_max: int = 600  # seconds
    # Per-tenant fairness: the most tasks a single tenant may have running at once.
    # Excess tasks yield the worker (re-queue) so one large agency cannot occupy
    # the whole pool and starve smaller tenants (02_Technical_Architecture §8).
    jobs_tenant_concurrency: int = 8
    # How long a yielded (over-cap) task waits before trying again.
    jobs_fairness_retry_delay: int = 5  # seconds
    # An in-flight slot is reclaimed after this long even if a worker dies mid-task
    # without releasing it, so a crash can't permanently shrink a tenant's quota.
    jobs_inflight_ttl_seconds: int = 3600
    # How long an idempotency claim is remembered (a duplicate submission inside
    # this window is suppressed).
    jobs_idempotency_ttl_seconds: int = 24 * 3600
    # Redis list that exhausted-retry tasks are parked on for inspection/replay.
    jobs_dead_letter_key: str = "jobs:dead_letter"

    # ── Google OAuth (GBP connection) ─────────────────────────────────────────
    # Obtain from Google Cloud Console → APIs & Services → Credentials.
    # Scope needed: https://www.googleapis.com/auth/business.manage
    # Raw tokens must never be stored in the DB — use vault.set_secret() and
    # persist only the returned token_ref (see CLAUDE.md hard rules, P1D-1).
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    # ── Token Vault ───────────────────────────────────────────────────────────
    # URL of the secret store (HashiCorp Vault, AWS Secrets Manager, etc.).
    # Leave empty in local dev to use the in-memory LocalDevVault stub (app/core/vault.py).
    vault_url: str = ""
    vault_kv_path: str = "secret/lumenlocal"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
