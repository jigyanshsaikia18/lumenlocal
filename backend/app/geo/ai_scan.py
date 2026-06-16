"""Turn an AI-visibility scan request into a persistable result (P2C-2).

The geo-grid-for-AI analogue of :mod:`app.geo.scan`: it lays out the grid, asks
an :class:`~app.geo.ai.base.AiSearchProvider` the prompt at each node (repeated
``sample_runs`` times for stability), and returns the ``matrix_results`` payload,
the rolled-up SAIV, and the deduped ``cited_sources`` — exactly the three things
``geo_ai_scans`` stores.

It does no I/O of its own beyond delegating to the injected provider, whose only
shipped implementation is the offline :class:`~app.geo.ai.mock.MockAiSearchProvider`
(live calls are deferred to real adapters under the Policy Compliance Engine and
the scanning-ToS caveat, ``/docs/01_PRD.md §11.1``). So the heavy logic stays
unit-testable without a broker, a database, or a network.

**Sampling across the grid.** AI answers are localized: the same intent ("best
plumber near me") returns a different answer depending on *where* it's asked. We
model that by qualifying the prompt with each node's coordinates before handing it
to the provider, so a node near a strong competitor can legitimately differ from
one across town. The user-facing ``prompt`` stored on the scan is the original,
unqualified one.
"""
from __future__ import annotations

from app.geo.ai.base import AiSearchProvider
from app.geo.ai.records import AiVisibilityRecord
from app.geo.grid import GridNode, compute_grid_nodes
from app.geo.saiv import compute_saiv

# A matrix entry: one node's coordinate plus its per-run visibility records. Shape
# matches the schema's "Coord → mention/prominence per run" for geo_ai_scans.
MatrixEntry = dict


def _localized_prompt(prompt: str, node: GridNode) -> str:
    """Qualify ``prompt`` with a node's location so the answer is point-specific.

    A lightweight stand-in for setting the AI tool's geolocation context per grid
    node; it makes the (deterministic) provider vary by node the way a real
    localized AI answer would.
    """
    return f"{prompt} (near {node.lat:.4f},{node.lon:.4f})"


def build_ai_matrix(
    lat: float,
    lon: float,
    radius_miles: float,
    dimensions: int,
    prompt: str,
    business_name: str,
    provider: AiSearchProvider,
    sample_runs: int = 1,
) -> tuple[list[MatrixEntry], float, list[str]]:
    """Compute a full geo-grid-for-AI scan result.

    Args:
        lat, lon: Center of the grid (the location's centroid).
        radius_miles: Distance from center to grid edge.
        dimensions: Grid size ``N`` → ``N × N`` nodes.
        prompt: The local prompt to sample (stored unqualified on the scan).
        business_name: The tracked business to look for in each answer.
        provider: The AI-search adapter to query (offline mock for now).
        sample_runs: How many times to repeat the query per node (stability).

    Returns:
        ``(matrix_results, saiv, cited_sources)`` where ``matrix_results`` has one
        entry per node ``{"row", "col", "lat", "lon", "runs": [...]}`` (each run a
        ``{"mentioned", "prominence"}``), ``saiv`` is the AI-Search Visibility
        (0–100, 2 dp) across every sample, and ``cited_sources`` is the
        order-preserving, deduped union of every source the AI referenced.

    Raises:
        ValueError: if ``sample_runs < 1`` (grid args validated by the grid math).
    """
    if sample_runs < 1:
        raise ValueError(f"sample_runs must be >= 1, got {sample_runs}")

    nodes = compute_grid_nodes(lat, lon, radius_miles, dimensions)
    matrix: list[MatrixEntry] = []
    samples: list[AiVisibilityRecord] = []
    cited: list[str] = []
    seen: set[str] = set()

    for node in nodes:
        node_prompt = _localized_prompt(prompt, node)
        runs: list[dict] = []
        for _ in range(sample_runs):
            record = provider.query(node_prompt, business_name=business_name)
            samples.append(record)
            runs.append({"mentioned": record.mentioned, "prominence": record.prominence})
            # Capture cited sources even when the business is absent (GEO-5):
            # "who is cited for this category" is itself the signal.
            for src in record.cited_sources:
                if src not in seen:
                    seen.add(src)
                    cited.append(src)
        matrix.append(
            {
                "row": node.row,
                "col": node.col,
                "lat": round(node.lat, 6),
                "lon": round(node.lon, 6),
                "runs": runs,
            }
        )

    return matrix, compute_saiv(samples), cited
