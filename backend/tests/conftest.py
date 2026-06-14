"""Shared pytest fixtures.

Ensures the database schema (including the P1A-2 RLS migration and the lumen_app
role) is applied before any test runs, so DB-backed tests are self-contained.
"""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session", autouse=True)
def _migrate_to_head() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(cfg, "head")
