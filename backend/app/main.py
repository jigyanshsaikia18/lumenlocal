"""LumenLocal FastAPI application entrypoint (P0-1 scaffold).

Exposes GET /health which verifies the app is up and pings Postgres + Redis so
the scaffold is end-to-end verifiable. Business routers are mounted from
app.api.v1 in later tickets.
"""
from __future__ import annotations

import redis
from fastapi import FastAPI
from sqlalchemy import create_engine, text

from app.api.v1 import api_router
from app.api.v1.deps import build_request_context
from app.core.config import settings
from app.core.errors import install_error_handlers
from app.security.deps import get_request_context

app = FastAPI(title="LumenLocal API", version="0.1.0")

install_error_handlers(app)
app.include_router(api_router, prefix="/api")

# Wire the RBAC principal seam (app.security.deps.get_request_context) to real JWT
# auth. The seam is a placeholder that 401s until bound here; without this every
# require(...)-gated route is unreachable even with a valid token. Tests override
# the same key with a fake principal, so this binding is production-only.
app.dependency_overrides[get_request_context] = build_request_context


def _check_postgres() -> str:
    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return "ok"
    except Exception as exc:  # noqa: BLE001 - report any failure to caller
        return f"error: {exc.__class__.__name__}"


def _check_redis() -> str:
    try:
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        client.ping()
        client.close()
        return "ok"
    except Exception as exc:  # noqa: BLE001 - report any failure to caller
        return f"error: {exc.__class__.__name__}"


@app.get("/health")
def health() -> dict:
    """Liveness + dependency check. Always returns 200; field values report status."""
    return {
        "status": "ok",
        "environment": settings.environment,
        "dependencies": {
            "postgres": _check_postgres(),
            "redis": _check_redis(),
        },
    }
