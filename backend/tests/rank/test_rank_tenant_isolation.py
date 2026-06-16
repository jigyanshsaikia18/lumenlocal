"""P2B-2 tenant isolation: rank-tracking endpoints must not cross tenants.

The handlers run on the privileged (RLS-bypassing) ``get_db`` session and the
rank tables are scoped to a tenant only transitively through ``location_id``, so
without an explicit ownership check a tenant-A principal could read or write a
tenant-B location's schedules/results by passing its UUID. These tests seed
tenant B as the superuser and exercise the real DB query path as a tenant-A
caller — they must all 404, never leak.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.v1.rank_tracking import RANK_FEATURE, router
from app.core.errors import install_error_handlers
from app.db.session import SessionLocal
from app.entitlements.cache import entitlement_cache
from app.entitlements.gateway import get_entitlement_service
from app.entitlements.repository import EntitlementService
from app.security.context import RequestContext, RoleAssignment
from app.security.deps import get_request_context
from tests.entitlements.fakes import FakeEntitlementBackend, feat


@pytest.fixture
def two_tenants_with_rank_data():
    """Seed tenant A and tenant B; tenant B owns a location + one rank result."""
    tenant_a, tenant_b = uuid4(), uuid4()
    client_b, location_b, result_b = uuid4(), uuid4(), uuid4()

    with SessionLocal() as s:
        for tid, tag in [(tenant_a, "A"), (tenant_b, "B")]:
            s.execute(
                text("INSERT INTO tenants (id, company_name) VALUES (:id, :n)"),
                {"id": tid, "n": f"Tenant {tag}"},
            )
        s.execute(
            text("INSERT INTO clients (id, tenant_id, name) VALUES (:id, :t, 'Client B')"),
            {"id": client_b, "t": tenant_b},
        )
        s.execute(
            text(
                "INSERT INTO locations (id, tenant_id, client_id, latitude, longitude) "
                "VALUES (:id, :t, :c, 40.0, -75.0)"
            ),
            {"id": location_b, "t": tenant_b, "c": client_b},
        )
        s.execute(
            text(
                "INSERT INTO keyword_rank_results "
                "(id, location_id, keyword, device, map_pack_rank, organic_rank) "
                "VALUES (:id, :loc, 'secret tenant-b keyword', 'desktop', 3, 7)"
            ),
            {"id": result_b, "loc": location_b},
        )
        s.commit()

    yield {"tenant_a": tenant_a, "location_b": location_b, "client_b": client_b}

    with SessionLocal() as s:
        s.execute(text("DELETE FROM keyword_rank_results WHERE id = :id"), {"id": result_b})
        s.execute(text("DELETE FROM keyword_rank_schedules WHERE location_id = :id"), {"id": location_b})
        s.execute(text("DELETE FROM locations WHERE id = :id"), {"id": location_b})
        s.execute(text("DELETE FROM clients WHERE id = :id"), {"id": client_b})
        s.execute(
            text("DELETE FROM tenants WHERE id IN (:a, :b)"),
            {"a": tenant_a, "b": tenant_b},
        )
        s.commit()


def _client_as_tenant_a(data) -> TestClient:
    entitlement_cache.clear()
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(router)

    principal = RequestContext(
        user_id=uuid4(),
        tenant_id=data["tenant_a"],
        roles=(RoleAssignment(role="account_manager"),),  # read + run capabilities
    )
    backend = FakeEntitlementBackend(
        [feat(RANK_FEATURE, default=True)],
        location_client={data["location_b"]: data["client_b"]},
    )
    app.dependency_overrides[get_request_context] = lambda: principal
    app.dependency_overrides[get_entitlement_service] = lambda: EntitlementService(backend)
    return TestClient(app)


def test_cannot_read_other_tenant_rank_results(two_tenants_with_rank_data):
    client = _client_as_tenant_a(two_tenants_with_rank_data)
    loc = two_tenants_with_rank_data["location_b"]
    resp = client.get(f"/locations/{loc}/keyword-rank-results")
    assert resp.status_code == 404
    assert "secret tenant-b keyword" not in resp.text


def test_cannot_list_other_tenant_schedules(two_tenants_with_rank_data):
    client = _client_as_tenant_a(two_tenants_with_rank_data)
    loc = two_tenants_with_rank_data["location_b"]
    resp = client.get(f"/locations/{loc}/keyword-rank-schedules")
    assert resp.status_code == 404


def test_cannot_create_schedule_on_other_tenant_location(two_tenants_with_rank_data):
    client = _client_as_tenant_a(two_tenants_with_rank_data)
    loc = two_tenants_with_rank_data["location_b"]
    resp = client.post(
        f"/locations/{loc}/keyword-rank-schedules",
        json={"keyword": "intrusion", "device": "desktop", "interval_hours": 168},
    )
    assert resp.status_code == 404
    # And nothing was written to tenant B's location.
    with SessionLocal() as s:
        count = s.execute(
            text("SELECT count(*) FROM keyword_rank_schedules WHERE location_id = :loc"),
            {"loc": loc},
        ).scalar()
    assert count == 0


def test_cannot_trigger_scan_on_other_tenant_location(two_tenants_with_rank_data):
    client = _client_as_tenant_a(two_tenants_with_rank_data)
    loc = two_tenants_with_rank_data["location_b"]
    resp = client.post(
        f"/locations/{loc}/keyword-rank-scans",
        json={"keyword": "intrusion", "device": "desktop"},
    )
    assert resp.status_code == 404
