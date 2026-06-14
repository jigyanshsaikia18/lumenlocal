"""Shared pytest fixtures.

Ensures the database schema (including the P1A-2 RLS migration and the lumen_app
role) is applied before any test runs, so DB-backed tests are self-contained.

If Postgres is unreachable (e.g. an unprovisioned dev box running only the
pure-Python unit suites), the migration is skipped with a warning rather than
hard-failing the whole session — DB-backed tests then fail on their own queries,
which keeps the signal clear instead of masking it.
"""
import os
import warnings
from pathlib import Path

# Set required env vars BEFORE any app module is imported during collection.
# SECRET_KEY has no default (startup fails clearly without it); tests use this
# insecure placeholder — it is never used for signing in production.
os.environ.setdefault("SECRET_KEY", "test-only-insecure-do-not-use-in-production")

import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session", autouse=True)
def _migrate_to_head() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    try:
        command.upgrade(cfg, "head")
    except Exception as exc:  # noqa: BLE001 - connectivity/driver issues only
        warnings.warn(
            f"Skipping DB migration ({exc.__class__.__name__}): Postgres unavailable. "
            "DB-backed tests will fail; pure-unit tests are unaffected.",
            stacklevel=2,
        )
