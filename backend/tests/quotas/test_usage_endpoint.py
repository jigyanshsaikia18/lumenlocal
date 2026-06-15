"""P1C-4 acceptance (API half): /usage reflects consumption; /quotas sets caps.

End-to-end over HTTP with no Postgres: the quota service is backed by one shared
in-memory store (so consumption recorded by a "worker" is visible to the endpoint),
the principal is a super_admin, and the request DB session is a no-op commit.
"""
from datetime import date
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.deps import get_db
from app.api.v1.quotas import get_quota_service, router
from app.core.errors import install_error_handlers
from app.quotas.service import (
    METRIC_GEOGRID_SCANS,
    ON_EXCEED_PAUSE,
    SCOPE_TENANT,
    QuotaService,
)
from app.security.context import RequestContext, RoleAssignment
from app.security.deps import get_request_context
from tests.quotas.fakes import FakeQuotaStore

TENANT = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
FIXED_DAY = date(2026, 6, 15)
PERIOD_START = "2026-06-01"


class DummySession:
    def commit(self) -> None:  # pragma: no cover - trivial
        pass


@pytest.fixture
def env():
    store = FakeQuotaStore()
    service = QuotaService(store, clock=lambda: FIXED_DAY)

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(router)

    principal = RequestContext(
        user_id=uuid4(), tenant_id=TENANT, roles=(RoleAssignment(role="super_admin"),)
    )
    app.dependency_overrides[get_request_context] = lambda: principal
    app.dependency_overrides[get_quota_service] = lambda: service
    app.dependency_overrides[get_db] = lambda: DummySession()

    return {"client": TestClient(app), "store": store, "service": service}


def _metrics(usage_body) -> dict:
    return {m["metric"]: m for m in usage_body["metrics"]}


def test_set_cap_then_usage_reflects_consumption(env):
    client, service = env["client"], env["service"]
    q = f"scope_type={SCOPE_TENANT}&scope_id={TENANT}"

    # Super-Admin sets a hard monthly cap of 2 geo-grid scans.
    put = client.put(f"/quotas?{q}", json={"metric": METRIC_GEOGRID_SCANS, "limit_value": 2})
    assert put.status_code == 200
    assert put.json()["limit_value"] == 2
    assert put.json()["on_exceed"] == ON_EXCEED_PAUSE

    # It shows up in the cap list.
    listing = client.get(f"/quotas?{q}").json()
    assert any(quota["metric"] == METRIC_GEOGRID_SCANS for quota in listing["quotas"])

    # Baseline: no consumption yet.
    usage = client.get(f"/usage?{q}").json()
    assert usage["period_start"] == PERIOD_START
    geogrid = _metrics(usage)[METRIC_GEOGRID_SCANS]
    assert geogrid == {
        "metric": METRIC_GEOGRID_SCANS, "used": 0, "limit": 2,
        "remaining": 2, "exceeded": False, "on_exceed": ON_EXCEED_PAUSE,
    }

    # A metered worker consumes up to the cap...
    assert service.consume(SCOPE_TENANT, TENANT, METRIC_GEOGRID_SCANS).allowed is True
    assert service.consume(SCOPE_TENANT, TENANT, METRIC_GEOGRID_SCANS).allowed is True
    # ...and the next consume is refused at the cap.
    assert service.consume(SCOPE_TENANT, TENANT, METRIC_GEOGRID_SCANS).allowed is False

    # /usage now reflects the consumption and the exhausted cap.
    geogrid = _metrics(client.get(f"/usage?{q}").json())[METRIC_GEOGRID_SCANS]
    assert geogrid["used"] == 2
    assert geogrid["remaining"] == 0
    assert geogrid["exceeded"] is True


def test_usage_lists_all_metered_metrics(env):
    client = env["client"]
    usage = client.get(f"/usage?scope_type={SCOPE_TENANT}&scope_id={TENANT}").json()
    metrics = _metrics(usage)
    assert {"google_api_calls", "geogrid_scans", "ai_scans", "llm_credits"} <= set(metrics)
    # Uncapped metrics report null limit/remaining.
    assert metrics["ai_scans"]["limit"] is None
    assert metrics["ai_scans"]["remaining"] is None


def test_invalid_scope_type_is_400(env):
    resp = env["client"].get(f"/usage?scope_type=galaxy&scope_id={TENANT}")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_scope_type"


def test_put_unknown_metric_is_400(env):
    resp = env["client"].put(
        f"/quotas?scope_type={SCOPE_TENANT}&scope_id={TENANT}",
        json={"metric": "not_a_metric", "limit_value": 5},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_quota"
