"""Application settings loaded from environment / .env (P0-3 will extend this)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"

    # Postgres
    # Privileged connection: migrations, admin, health. Owns the schema and (in dev)
    # is a superuser, so it BYPASSES row-level security. Never use it for request handling.
    database_url: str = "postgresql+psycopg://lumen:lumen_dev_password@localhost:5432/lumenlocal"

    # Application connection: a non-superuser role that IS subject to row-level security.
    # Every tenant-scoped runtime query goes through this role (see app.db.session).
    app_database_url: str = (
        "postgresql+psycopg://lumen_app:lumen_app_dev_password@localhost:5432/lumenlocal"
    )

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Jobs / queue framework (P2A-1)
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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
