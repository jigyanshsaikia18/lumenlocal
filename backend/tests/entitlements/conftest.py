"""Keep the process-global entitlement cache from leaking across tests."""
import pytest

from app.entitlements.cache import entitlement_cache


@pytest.fixture(autouse=True)
def _clear_entitlement_cache():
    entitlement_cache.clear()
    yield
    entitlement_cache.clear()
