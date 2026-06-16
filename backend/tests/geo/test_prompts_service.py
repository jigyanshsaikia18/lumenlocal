"""P2C-4: GeoPromptService — unit tests (DB-backed).

Tests the service's interaction with the database:
- list_prompts returns defaults + custom for the tenant
- list_prompts filters by niche correctly
- add_custom_prompt persists and is scoped to tenant
- Custom prompts are not visible to other tenants (via RLS)
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.session import SessionLocal
from app.geo.prompts import GeoPromptService
from app.models.geo_prompt import GeoPrompt


def _seed_defaults():
    """Seed the database with some default prompts (superuser context)."""
    with SessionLocal() as db:
        defaults = [
            GeoPrompt(niche=None, prompt="best {category} near me", is_custom=False, tenant_id=None),
            GeoPrompt(niche="plumber", prompt="emergency plumber {area}", is_custom=False, tenant_id=None),
            GeoPrompt(niche="restaurant", prompt="best restaurant {area}", is_custom=False, tenant_id=None),
        ]
        for p in defaults:
            db.add(p)
        db.commit()


@pytest.fixture
def tenant_1():
    return uuid4()


@pytest.fixture
def tenant_2():
    return uuid4()


@pytest.fixture(autouse=True)
def _seed_and_cleanup():
    """Seed defaults, run test, cleanup all prompts."""
    _seed_defaults()
    yield
    with SessionLocal() as db:
        db.query(GeoPrompt).delete()
        db.commit()


def test_list_prompts_returns_defaults(tenant_1):
    """list_prompts returns default prompts visible to all tenants."""
    with SessionLocal() as db:
        service = GeoPromptService(db)
        prompts = service.list_prompts(tenant_1)
        assert len(prompts) == 3
        assert all(not p.is_custom for p in prompts)


def test_list_prompts_filters_by_niche(tenant_1):
    """list_prompts filters by niche."""
    with SessionLocal() as db:
        service = GeoPromptService(db)
        prompts = service.list_prompts(tenant_1, niche="plumber")
        assert len(prompts) == 1
        assert prompts[0].niche == "plumber"


def test_add_custom_prompt(tenant_1):
    """add_custom_prompt saves a custom prompt scoped to the tenant."""
    with SessionLocal() as db:
        service = GeoPromptService(db)
        prompt = service.add_custom_prompt(tenant_1, "dentist", "best dentist near me")
        assert prompt.is_custom is True
        assert prompt.tenant_id == tenant_1
        assert prompt.niche == "dentist"

        # Verify it's in the database
        stored = db.query(GeoPrompt).filter(GeoPrompt.id == prompt.id).one()
        assert stored.is_custom is True
        assert stored.tenant_id == tenant_1


def test_add_custom_prompt_with_null_niche(tenant_1):
    """add_custom_prompt accepts niche=None for global custom prompts."""
    with SessionLocal() as db:
        service = GeoPromptService(db)
        prompt = service.add_custom_prompt(tenant_1, None, "find services near me")
        assert prompt.niche is None
        assert prompt.is_custom is True
        assert prompt.tenant_id == tenant_1


def test_custom_prompts_visible_to_owning_tenant(tenant_1, tenant_2):
    """Custom prompts are visible to the owning tenant."""
    with SessionLocal() as db:
        service = GeoPromptService(db)
        # Tenant 1 adds a custom prompt
        service.add_custom_prompt(tenant_1, "hvac", "emergency ac repair")

        # Tenant 1 can see it
        prompts_t1 = service.list_prompts(tenant_1)
        assert any(p.is_custom and p.niche == "hvac" for p in prompts_t1)


def test_custom_prompts_not_visible_to_other_tenants(tenant_1, tenant_2):
    """Custom prompts are not visible to other tenants."""
    with SessionLocal() as db:
        service = GeoPromptService(db)
        # Tenant 1 adds a custom prompt
        service.add_custom_prompt(tenant_1, "hvac", "emergency ac repair")

        # Tenant 2 can only see defaults, not tenant 1's custom
        prompts_t2 = service.list_prompts(tenant_2)
        assert not any(p.is_custom and p.tenant_id == tenant_1 for p in prompts_t2)
        # But tenant 2 still sees the defaults
        assert len(prompts_t2) == 3


def test_list_filters_and_custom_combined(tenant_1, tenant_2):
    """Listing custom + defaults filtered by niche."""
    with SessionLocal() as db:
        service = GeoPromptService(db)
        # Tenant 1 adds two custom plumber prompts
        service.add_custom_prompt(tenant_1, "plumber", "24/7 plumbing")
        service.add_custom_prompt(tenant_1, "plumber", "emergency drain repair")

        # Query for plumber prompts
        prompts_t1 = service.list_prompts(tenant_1, niche="plumber")
        # Should have 1 default + 2 custom
        assert len(prompts_t1) == 3
        assert all(p.niche == "plumber" for p in prompts_t1)

        # Count custom vs default
        defaults = [p for p in prompts_t1 if not p.is_custom]
        customs = [p for p in prompts_t1 if p.is_custom]
        assert len(defaults) == 1
        assert len(customs) == 2

        # Tenant 2 only sees the default plumber prompt
        prompts_t2 = service.list_prompts(tenant_2, niche="plumber")
        assert len(prompts_t2) == 1
        assert not prompts_t2[0].is_custom
