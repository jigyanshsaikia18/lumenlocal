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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
