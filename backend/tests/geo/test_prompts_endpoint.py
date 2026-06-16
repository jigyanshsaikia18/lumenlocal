"""P2C-4: GET/POST /geo-prompts — niche-aware defaults + custom (API spec §6, §12).

Tests the endpoint contract:
- GET /geo-prompts lists defaults + custom visible to the tenant
- GET /geo-prompts?niche=X filters by niche
- POST /geo-prompts creates a custom prompt scoped to the tenant
- Feature gating (403 feature_disabled when off)
- RBAC: geo_prompts.write requires account_manager+ role
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.geo_prompts import (
    GEO_PROMPTS_FEATURE,
    get_geo_prompt_service,
    router,
)
from app.core.errors import install_error_handlers
from app.entitlements.cache import entitlement_cache
from app.entitlements.gateway import get_entitlement_service
from app.entitlements.repository import EntitlementService
from app.geo.prompts import GeoPromptService
from app.models.geo_prompt import GeoPrompt
from app.security.context import RequestContext, RoleAssignment
from app.security.deps import get_request_context
from tests.entitlements.fakes import FakeEntitlementBackend, feat

TENANT_1_ID = UUID("c0000000-0000-0000-0000-000000000001")
TENANT_2_ID = UUID("c0000000-0000-0000-0000-000000000002")

_FEATURES = [feat(GEO_PROMPTS_FEATURE, default=True)]


@pytest.fixture(autouse=True)
def _clear_entitlement_cache():
    entitlement_cache.clear()
    yield
    entitlement_cache.clear()


def _principal(tenant_id: UUID, role: str) -> RequestContext:
    """Build a principal with the given tenant and role."""
    return RequestContext(
        user_id=uuid4(),
        tenant_id=tenant_id,
        roles=(RoleAssignment(role=role),),
    )


class _FakeGeoPromptService(GeoPromptService):
    """In-memory prompt store for testing (no DB)."""

    def __init__(self):
        self.prompts = [
            GeoPrompt(
                id=UUID("10000000-0000-0000-0000-000000000001"),
                niche=None,
                prompt="best {category} near me",
                is_custom=False,
                tenant_id=None,
            ),
            GeoPrompt(
                id=UUID("10000000-0000-0000-0000-000000000002"),
                niche="plumber",
                prompt="emergency plumber {area}",
                is_custom=False,
                tenant_id=None,
            ),
            GeoPrompt(
                id=UUID("20000000-0000-0000-0000-000000000001"),
                niche="restaurant",
                prompt="best restaurant {area}",
                is_custom=False,
                tenant_id=None,
            ),
            # Custom prompt for tenant 1
            GeoPrompt(
                id=UUID("30000000-0000-0000-0000-000000000001"),
                niche="plumber",
                prompt="24/7 plumbing emergency {city}",
                is_custom=True,
                tenant_id=TENANT_1_ID,
            ),
        ]

    def list_prompts(self, tenant_id, niche=None):
        """List defaults + custom visible to tenant, optionally filtered by niche."""
        result = [p for p in self.prompts if not p.is_custom or p.tenant_id == tenant_id]
        if niche:
            result = [p for p in result if p.niche == niche]
        return result

    def add_custom_prompt(self, tenant_id, niche, prompt):
        """Add a custom prompt (in-memory for test)."""
        new_prompt = GeoPrompt(
            id=uuid4(),
            niche=niche,
            prompt=prompt,
            is_custom=True,
            tenant_id=tenant_id,
        )
        self.prompts.append(new_prompt)
        return new_prompt


def _build_app(*, feature_enabled: bool, principal_role: str) -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(router)

    client_overrides = {} if feature_enabled else {None: {GEO_PROMPTS_FEATURE: False}}
    backend = FakeEntitlementBackend(_FEATURES, client=client_overrides)

    app.dependency_overrides[get_request_context] = lambda: _principal(TENANT_1_ID, principal_role)
    app.dependency_overrides[get_entitlement_service] = lambda: EntitlementService(backend)
    app.dependency_overrides[get_geo_prompt_service] = _FakeGeoPromptService

    return app


def test_list_prompts_returns_200_with_defaults_plus_custom():
    """GET /geo-prompts returns both defaults + tenant's custom prompts."""
    client = TestClient(_build_app(feature_enabled=True, principal_role="analyst"))
    resp = client.get("/geo-prompts")
    assert resp.status_code == 200
    body = resp.json()

    assert "prompts" in body
    prompts = body["prompts"]
    assert len(prompts) >= 4  # At least the 3 defaults + 1 custom for tenant 1

    # Check we have the defaults and the custom prompt
    prompt_texts = [p["prompt"] for p in prompts]
    assert "best {category} near me" in prompt_texts
    assert "emergency plumber {area}" in prompt_texts
    assert "24/7 plumbing emergency {city}" in prompt_texts
    # Tenant 2's custom prompts should NOT be visible
    assert "only_visible_to_tenant_2" not in prompt_texts

    # is_custom flags present
    defaults = [p for p in prompts if not p["is_custom"]]
    customs = [p for p in prompts if p["is_custom"]]
    assert len(defaults) >= 3
    assert len(customs) >= 1


def test_list_prompts_filters_by_niche():
    """GET /geo-prompts?niche=X filters by niche."""
    client = TestClient(_build_app(feature_enabled=True, principal_role="analyst"))
    resp = client.get("/geo-prompts?niche=plumber")
    assert resp.status_code == 200
    body = resp.json()

    prompts = body["prompts"]
    # Should have the default plumber prompt + custom plumber prompt
    assert len(prompts) == 2
    assert all(p["niche"] == "plumber" for p in prompts)
    # Verify we have both default and custom
    assert any(not p["is_custom"] for p in prompts)
    assert any(p["is_custom"] for p in prompts)


def test_list_prompts_feature_disabled_returns_403():
    """GET /geo-prompts returns 403 feature_disabled when feature is off."""
    client = TestClient(_build_app(feature_enabled=False, principal_role="analyst"))
    resp = client.get("/geo-prompts")
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"]["code"] == "feature_disabled"


def test_create_prompt_requires_account_manager_role():
    """POST /geo-prompts requires account_manager+ role."""
    # analyst should fail (doesn't have geo_prompts.write)
    client_analyst = TestClient(_build_app(feature_enabled=True, principal_role="analyst"))
    resp = client_analyst.post("/geo-prompts", json={"niche": "dentist", "prompt": "best dentist near me"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"

    # account_manager should succeed
    client_manager = TestClient(_build_app(feature_enabled=True, principal_role="account_manager"))
    resp = client_manager.post("/geo-prompts", json={"niche": "dentist", "prompt": "best dentist near me"})
    assert resp.status_code == 201


def test_create_prompt_returns_201():
    """POST /geo-prompts returns 201 with the created prompt."""
    client = TestClient(_build_app(feature_enabled=True, principal_role="account_manager"))
    payload = {"niche": "dentist", "prompt": "best dentist near me"}
    resp = client.post("/geo-prompts", json=payload)
    assert resp.status_code == 201
    body = resp.json()

    assert "id" in body
    assert body["niche"] == "dentist"
    assert body["prompt"] == "best dentist near me"
    assert body["is_custom"] is True


def test_create_prompt_with_null_niche():
    """POST /geo-prompts accepts niche=null for global custom prompts."""
    client = TestClient(_build_app(feature_enabled=True, principal_role="account_manager"))
    payload = {"niche": None, "prompt": "find services near me"}
    resp = client.post("/geo-prompts", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["niche"] is None
    assert body["is_custom"] is True


def test_custom_prompts_are_tenant_scoped():
    """Custom prompts created by tenant 1 are only visible to tenant 1."""
    # Tenant 1 creates a custom prompt
    client_t1 = TestClient(
        _build_app(feature_enabled=True, principal_role="account_manager")
    )
    client_t1.post("/geo-prompts", json={"niche": "hvac", "prompt": "emergency ac repair"})

    # Tenant 1 can see it
    resp_t1 = client_t1.get("/geo-prompts?niche=hvac")
    prompts_t1 = resp_t1.json()["prompts"]
    assert any(p["is_custom"] for p in prompts_t1)

    # Tenant 2 cannot see it
    app_t2 = _build_app(feature_enabled=True, principal_role="analyst")

    def _principal_t2() -> RequestContext:
        return _principal(TENANT_2_ID, "analyst")

    app_t2.dependency_overrides[get_request_context] = _principal_t2
    client_t2 = TestClient(app_t2)
    resp_t2 = client_t2.get("/geo-prompts?niche=hvac")
    prompts_t2 = resp_t2.json()["prompts"]
    # Tenant 2 sees only the defaults, no custom from tenant 1
    assert all(not p["is_custom"] for p in prompts_t2)
