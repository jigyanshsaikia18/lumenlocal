/**
 * Pure rollup and filter utilities for the multi-location command center
 * (PRD §7 D-3, P1E-2). No I/O — directly unit-testable.
 */
import type { LocationKPIs, LocationSummary } from "./types";

export type HealthFilter = "all" | "good" | "warning" | "critical";

/** Classify a 0–100 health score into a display tier. */
export function healthStatus(score: number): "good" | "warning" | "critical" {
  if (score >= 80) return "good";
  if (score >= 50) return "warning";
  return "critical";
}

/** Keep only locations whose health score matches the chosen filter. */
export function filterLocations(
  locations: LocationSummary[],
  filter: HealthFilter,
): LocationSummary[] {
  if (filter === "all") return locations;
  return locations.filter((loc) => healthStatus(loc.health_score) === filter);
}

/** Sum KPIs element-wise across an array of locations. */
export function computeRollup(locations: LocationSummary[]): LocationKPIs {
  return locations.reduce(
    (acc, loc) => ({
      views: acc.views + loc.kpis.views,
      calls: acc.calls + loc.kpis.calls,
      directions: acc.directions + loc.kpis.directions,
      website_clicks: acc.website_clicks + loc.kpis.website_clicks,
    }),
    { views: 0, calls: 0, directions: 0, website_clicks: 0 },
  );
}

/** Count how many locations fall into each health filter bucket. */
export function countByFilter(
  locations: LocationSummary[],
): Record<HealthFilter, number> {
  return {
    all: locations.length,
    good: filterLocations(locations, "good").length,
    warning: filterLocations(locations, "warning").length,
    critical: filterLocations(locations, "critical").length,
  };
}
