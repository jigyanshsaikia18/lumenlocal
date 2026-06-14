"""Feature registry: the in-memory shape of the ``features`` table + its validation.

A ``FeatureDef`` is one registered capability (PRD §5 FT-1): a stable key, a
display name, its prerequisite feature keys, and the platform default state.
``validate_registry`` guards the dependency graph itself — every dependency must
resolve to a known feature and the graph must be acyclic — so a misconfigured
registry fails loudly at load rather than producing nonsense at resolution.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field


class RegistryError(Exception):
    """The feature registry is internally inconsistent (unknown dep or a cycle)."""


@dataclass(frozen=True)
class FeatureDef:
    """One registered feature flag (mirrors a ``features`` row)."""

    key: str
    name: str
    dependencies: tuple[str, ...] = field(default=())
    default_state: bool = False

    def __post_init__(self) -> None:
        # Accept any iterable of keys but store an immutable tuple.
        if not isinstance(self.dependencies, tuple):
            object.__setattr__(self, "dependencies", tuple(self.dependencies))


def validate_registry(features: Iterable[FeatureDef]) -> None:
    """Raise ``RegistryError`` if any dependency is unknown or the graph has a cycle."""
    feats = list(features)
    by_key = index_by_key(feats)

    # 1. Every dependency must point at a registered feature.
    for f in feats:
        for dep in f.dependencies:
            if dep not in by_key:
                raise RegistryError(
                    f"feature {f.key!r} depends on unknown feature {dep!r}"
                )

    # 2. The dependency graph must be acyclic (a self-dependency is a 1-cycle).
    WHITE, GRAY, BLACK = 0, 1, 2
    color = dict.fromkeys(by_key, WHITE)

    def visit(key: str) -> None:
        color[key] = GRAY
        for dep in by_key[key].dependencies:
            if color[dep] == GRAY:
                raise RegistryError(f"dependency cycle involving {dep!r}")
            if color[dep] == WHITE:
                visit(dep)
        color[key] = BLACK

    for key in by_key:
        if color[key] == WHITE:
            visit(key)


def index_by_key(features: Sequence[FeatureDef]) -> dict[str, FeatureDef]:
    """Map feature key → definition (helper shared by the resolver)."""
    return {f.key: f for f in features}
