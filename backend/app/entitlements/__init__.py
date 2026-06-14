"""Entitlement engine — the client-wise feature-toggle resolver (PRD §5).

Resolution precedence (most specific wins): ``location > client > plan > default``,
with dependency force-off (FT-4). Public surface:

- ``resolve_entitlements`` / ``ResolvedFeature`` — the pure resolver.
- ``validate_registry`` / ``validate_can_enable`` — dependency-graph guards.
- ``FeatureDef`` — the registry shape.
- ``EntitlementService`` / ``OverrideStore`` / ``SqlAlchemyOverrideStore`` — DB seam.
"""
from app.entitlements.registry import FeatureDef, RegistryError, validate_registry
from app.entitlements.repository import (
    EntitlementService,
    OverrideStore,
    SqlAlchemyOverrideStore,
)
from app.entitlements.resolver import (
    DependencyError,
    ResolvedFeature,
    resolve_entitlements,
    validate_can_enable,
)

__all__ = [
    "DependencyError",
    "EntitlementService",
    "FeatureDef",
    "OverrideStore",
    "RegistryError",
    "ResolvedFeature",
    "SqlAlchemyOverrideStore",
    "resolve_entitlements",
    "validate_can_enable",
    "validate_registry",
]
