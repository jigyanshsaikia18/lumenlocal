"""P0-1 scaffold test: the app boots and /health responds 200.

Dependency pings (postgres/redis) are reported in the body but not asserted here,
so this test passes without infra running. Infra connectivity is verified manually
via `docker compose up` per the ticket.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "postgres" in body["dependencies"]
    assert "redis" in body["dependencies"]
