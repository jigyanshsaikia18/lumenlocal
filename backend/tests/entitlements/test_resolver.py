"""P1C-1: the pure entitlement resolver.

Covers all four precedence levels (location > client > plan > default), the
dependency force-off rule, the write guard, and registry validation. No DB —
this is the pure core; the DB-mocked integration lives in
``test_entitlement_service.py``.
"""
import pytest

from app.entitlements.registry import FeatureDef, RegistryError, validate_registry
from app.entitlements.resolver import (
    SOURCE_CLIENT,
    SOURCE_DEFAULT,
    SOURCE_DEPENDENCY,
    SOURCE_LOCATION,
    SOURCE_PLAN,
    DependencyError,
    resolve_entitlements,
    validate_can_enable,
)


def feat(key, deps=(), default=False):
    return FeatureDef(key=key, name=key.replace("_", " ").title(), dependencies=deps, default_state=default)


# Independent features (no deps) isolate precedence from the dependency rule.
# geogrid defaults OFF; protection defaults ON (so we test overriding both ways).
SIMPLE = [feat("geogrid", default=False), feat("protection", default=True)]

# A dependency edge: ai_writer requires review_inbox (FT-4 example).
REVIEW = feat("review_inbox", default=False)
AI_WRITER = feat("ai_writer", deps=("review_inbox",), default=False)
DEP = [REVIEW, AI_WRITER]


# --- Precedence: one test per level --------------------------------------------
def test_level_default_when_no_overrides():
    """Level 4 (broadest): with no overrides, each feature takes its default_state."""
    resolved = resolve_entitlements(SIMPLE)
    assert (resolved["geogrid"].enabled, resolved["geogrid"].source) == (False, SOURCE_DEFAULT)
    assert (resolved["protection"].enabled, resolved["protection"].source) == (True, SOURCE_DEFAULT)


def test_level_plan_beats_default():
    """Level 3: a plan override wins over default — both turning on and off."""
    resolved = resolve_entitlements(
        SIMPLE, plan_overrides={"geogrid": True, "protection": False}
    )
    assert (resolved["geogrid"].enabled, resolved["geogrid"].source) == (True, SOURCE_PLAN)
    assert (resolved["protection"].enabled, resolved["protection"].source) == (False, SOURCE_PLAN)


def test_level_client_beats_plan():
    """Level 2: a client override wins over the plan."""
    resolved = resolve_entitlements(
        SIMPLE,
        plan_overrides={"geogrid": True},
        client_overrides={"geogrid": False},
    )
    assert (resolved["geogrid"].enabled, resolved["geogrid"].source) == (False, SOURCE_CLIENT)


def test_level_location_beats_client():
    """Level 1 (most specific): a location override wins over client and plan."""
    resolved = resolve_entitlements(
        SIMPLE,
        plan_overrides={"geogrid": False},
        client_overrides={"geogrid": False},
        location_overrides={"geogrid": True},
    )
    assert (resolved["geogrid"].enabled, resolved["geogrid"].source) == (True, SOURCE_LOCATION)


def test_precedence_is_per_feature():
    """Different features in one resolve can settle at different levels."""
    resolved = resolve_entitlements(
        SIMPLE,
        plan_overrides={"protection": False},  # protection decided at plan
        location_overrides={"geogrid": True},  # geogrid decided at location
    )
    assert resolved["geogrid"].source == SOURCE_LOCATION
    assert resolved["protection"].source == SOURCE_PLAN


# --- Dependency rule (FT-4) ----------------------------------------------------
def test_dependent_forced_off_when_dependency_off():
    """ai_writer enabled at location but review_inbox off (default) → forced OFF."""
    resolved = resolve_entitlements(DEP, location_overrides={"ai_writer": True})
    assert resolved["review_inbox"].enabled is False
    assert resolved["ai_writer"].enabled is False
    assert resolved["ai_writer"].source == SOURCE_DEPENDENCY


def test_dependent_on_when_dependency_on():
    """Enable both → the dependent stays ON and keeps its own source."""
    resolved = resolve_entitlements(
        DEP,
        client_overrides={"review_inbox": True},
        location_overrides={"ai_writer": True},
    )
    assert resolved["review_inbox"].enabled is True
    assert (resolved["ai_writer"].enabled, resolved["ai_writer"].source) == (True, SOURCE_LOCATION)


def test_dependency_force_off_is_transitive():
    """a → b → c: if c is off, both b and a are forced off."""
    chain = [
        feat("c", default=False),
        feat("b", deps=("c",), default=False),
        feat("a", deps=("b",), default=False),
    ]
    resolved = resolve_entitlements(
        chain, location_overrides={"a": True, "b": True}  # c stays off
    )
    assert resolved["b"].enabled is False and resolved["b"].source == SOURCE_DEPENDENCY
    assert resolved["a"].enabled is False and resolved["a"].source == SOURCE_DEPENDENCY
    # Turning c on lets the whole chain resolve on.
    resolved2 = resolve_entitlements(
        chain, location_overrides={"a": True, "b": True, "c": True}
    )
    assert all(resolved2[k].enabled for k in ("a", "b", "c"))


def test_validate_can_enable_raises_when_dependency_off():
    resolved = resolve_entitlements(DEP)  # review_inbox off
    with pytest.raises(DependencyError):
        validate_can_enable("ai_writer", resolved, DEP)


def test_validate_can_enable_passes_when_dependency_on():
    resolved = resolve_entitlements(DEP, client_overrides={"review_inbox": True})
    validate_can_enable("ai_writer", resolved, DEP)  # no raise


# --- Registry validation -------------------------------------------------------
def test_validate_registry_accepts_valid_graph():
    validate_registry(DEP)  # no raise


def test_validate_registry_rejects_unknown_dependency():
    with pytest.raises(RegistryError):
        validate_registry([feat("ai_writer", deps=("does_not_exist",))])


def test_validate_registry_rejects_cycle():
    cyclic = [feat("a", deps=("b",)), feat("b", deps=("a",))]
    with pytest.raises(RegistryError):
        validate_registry(cyclic)


def test_validate_registry_rejects_self_dependency():
    with pytest.raises(RegistryError):
        validate_registry([feat("a", deps=("a",))])
