"""The pure entitlement resolver (PRD §5).

Turns the feature registry + the three override layers into a resolved on/off set.
No DB, no I/O — callers fetch the override maps (via an ``OverrideStore``) and pass
them in, which makes this the easily-unit-tested heart of the toggle engine.

Two rules, applied in order, per feature:

1. **Precedence** — most specific wins: ``location > client > plan > default``.
2. **Dependency force-off** (FT-4) — a feature resolves ON only if every
   dependency also resolves ON. An explicitly-enabled feature whose dependency
   is off is forced OFF, with ``source="dependency"`` recording why.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.entitlements.registry import FeatureDef, index_by_key

# Where a resolved value came from — useful for the "what this client sees"
# preview (FT-7) and for asserting precedence in tests.
SOURCE_LOCATION = "location"
SOURCE_CLIENT = "client"
SOURCE_PLAN = "plan"
SOURCE_DEFAULT = "default"
SOURCE_DEPENDENCY = "dependency"


class DependencyError(Exception):
    """An attempted toggle would create a dependency-inconsistent state (FT-4)."""


class ResolvedFeature:
    """The resolved state of one feature, plus where the decision came from."""

    __slots__ = ("key", "enabled", "source")

    def __init__(self, key: str, enabled: bool, source: str) -> None:
        self.key = key
        self.enabled = enabled
        self.source = source

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"ResolvedFeature(key={self.key!r}, enabled={self.enabled}, source={self.source!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ResolvedFeature):
            return NotImplemented
        return (self.key, self.enabled, self.source) == (other.key, other.enabled, other.source)


def resolve_entitlements(
    features: Sequence[FeatureDef],
    *,
    plan_overrides: Mapping[str, bool] | None = None,
    client_overrides: Mapping[str, bool] | None = None,
    location_overrides: Mapping[str, bool] | None = None,
) -> dict[str, ResolvedFeature]:
    """Resolve every feature to on/off via precedence then dependency force-off."""
    plan = plan_overrides or {}
    client = client_overrides or {}
    location = location_overrides or {}
    by_key = index_by_key(features)

    # Step 1 — precedence: location > client > plan > default (most specific wins).
    raw: dict[str, tuple[bool, str]] = {}
    for f in features:
        if f.key in location:
            raw[f.key] = (location[f.key], SOURCE_LOCATION)
        elif f.key in client:
            raw[f.key] = (client[f.key], SOURCE_CLIENT)
        elif f.key in plan:
            raw[f.key] = (plan[f.key], SOURCE_PLAN)
        else:
            raw[f.key] = (f.default_state, SOURCE_DEFAULT)

    # Step 2 — dependency force-off: a feature is effectively on only if every
    # dependency is too. Memoised DFS; a raw-on feature whose dependency is off
    # becomes off with source="dependency". Cycle-guarded for safety even though
    # validate_registry rejects cyclic graphs.
    result: dict[str, ResolvedFeature] = {}
    visiting: set[str] = set()

    def effective(key: str) -> bool:
        if key in result:
            return result[key].enabled
        enabled, source = raw[key]
        deps = by_key[key].dependencies if key in by_key else ()
        if enabled and deps and key not in visiting:
            visiting.add(key)
            deps_ok = all(effective(dep) for dep in deps if dep in by_key)
            visiting.discard(key)
            if not deps_ok:
                enabled, source = False, SOURCE_DEPENDENCY
        result[key] = ResolvedFeature(key, enabled, source)
        return enabled

    for f in features:
        effective(f.key)
    return result


def validate_can_enable(
    feature_key: str,
    resolved: Mapping[str, ResolvedFeature],
    features: Sequence[FeatureDef],
) -> None:
    """Write guard: raise ``DependencyError`` if a dependency of ``feature_key`` is off.

    Used by the override-write path (P1C-2) before persisting an "enable" so the
    admin gets a clear error instead of a silently-forced-off toggle.
    """
    by_key = index_by_key(features)
    feature = by_key.get(feature_key)
    if feature is None:
        raise DependencyError(f"unknown feature {feature_key!r}")
    missing = [
        dep
        for dep in feature.dependencies
        if not (dep in resolved and resolved[dep].enabled)
    ]
    if missing:
        raise DependencyError(
            f"cannot enable {feature_key!r}: dependencies not enabled: {missing}"
        )


# Re-exported so callers import the helper from one place.
__all__ = [
    "DependencyError",
    "ResolvedFeature",
    "SOURCE_CLIENT",
    "SOURCE_DEFAULT",
    "SOURCE_DEPENDENCY",
    "SOURCE_LOCATION",
    "SOURCE_PLAN",
    "index_by_key",
    "resolve_entitlements",
    "validate_can_enable",
]
