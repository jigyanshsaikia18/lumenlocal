import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  CommandCenterWidget,
  MULTI_LOCATION_FEATURE,
} from "@/components/dashboard/CommandCenterWidget";
import { FeatureFlagProvider } from "@/components/feature-flags/FeatureFlagProvider";
import {
  computeRollup,
  filterLocations,
  healthStatus,
} from "@/lib/dashboard/rollup";
import { sampleCommandCenter } from "@/lib/dashboard/sample";

// ---------------------------------------------------------------------------
// Pure utility: healthStatus
// ---------------------------------------------------------------------------

describe("healthStatus", () => {
  it("returns 'good' for score ≥ 80", () => {
    expect(healthStatus(80)).toBe("good");
    expect(healthStatus(100)).toBe("good");
  });

  it("returns 'warning' for score 50–79", () => {
    expect(healthStatus(50)).toBe("warning");
    expect(healthStatus(79)).toBe("warning");
  });

  it("returns 'critical' for score < 50", () => {
    expect(healthStatus(49)).toBe("critical");
    expect(healthStatus(0)).toBe("critical");
  });
});

// ---------------------------------------------------------------------------
// Pure utility: computeRollup
// ---------------------------------------------------------------------------

describe("computeRollup", () => {
  const { locations } = sampleCommandCenter;

  it("sums each KPI field across all locations", () => {
    const rollup = computeRollup(locations);
    expect(rollup.views).toBe(locations.reduce((s, l) => s + l.kpis.views, 0));
    expect(rollup.calls).toBe(locations.reduce((s, l) => s + l.kpis.calls, 0));
    expect(rollup.directions).toBe(
      locations.reduce((s, l) => s + l.kpis.directions, 0),
    );
    expect(rollup.website_clicks).toBe(
      locations.reduce((s, l) => s + l.kpis.website_clicks, 0),
    );
  });

  it("returns zeros for an empty list", () => {
    const r = computeRollup([]);
    expect(r.views).toBe(0);
    expect(r.calls).toBe(0);
    expect(r.directions).toBe(0);
    expect(r.website_clicks).toBe(0);
  });

  it("rollup matches the pre-computed sample total (regression guard)", () => {
    const rollup = computeRollup(locations);
    expect(rollup.views).toBe(sampleCommandCenter.rollup.views);
    expect(rollup.calls).toBe(sampleCommandCenter.rollup.calls);
    expect(rollup.directions).toBe(sampleCommandCenter.rollup.directions);
    expect(rollup.website_clicks).toBe(sampleCommandCenter.rollup.website_clicks);
  });
});

// ---------------------------------------------------------------------------
// Pure utility: filterLocations
// ---------------------------------------------------------------------------

describe("filterLocations", () => {
  const { locations } = sampleCommandCenter;

  it("returns all locations for filter 'all'", () => {
    expect(filterLocations(locations, "all")).toHaveLength(locations.length);
  });

  it("returns only good locations (score ≥ 80) for filter 'good'", () => {
    const good = filterLocations(locations, "good");
    expect(good.every((l) => l.health_score >= 80)).toBe(true);
    // sample has exactly 1 good location (Downtown Branch, 88)
    expect(good).toHaveLength(1);
  });

  it("returns only warning locations (50–79) for filter 'warning'", () => {
    const warn = filterLocations(locations, "warning");
    expect(warn.every((l) => l.health_score >= 50 && l.health_score < 80)).toBe(true);
    // sample has 2 warning locations (Mission 74, SoMa 61)
    expect(warn).toHaveLength(2);
  });

  it("returns only critical locations (< 50) for filter 'critical'", () => {
    const crit = filterLocations(locations, "critical");
    expect(crit.every((l) => l.health_score < 50)).toBe(true);
    // sample has 2 critical locations (Nob Hill 42, Sunset 33)
    expect(crit).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// React: feature-flag gating (PRD §7 D-6)
// ---------------------------------------------------------------------------

describe("CommandCenterWidget feature gating", () => {
  it("hides the widget entirely when the feature flag is off", () => {
    render(
      <FeatureFlagProvider flags={{ [MULTI_LOCATION_FEATURE]: false }}>
        <CommandCenterWidget data={sampleCommandCenter} />
      </FeatureFlagProvider>,
    );
    expect(screen.queryByText("Location Overview")).not.toBeInTheDocument();
  });

  it("renders the widget when the feature flag is on", () => {
    render(
      <FeatureFlagProvider flags={{ [MULTI_LOCATION_FEATURE]: true }}>
        <CommandCenterWidget data={sampleCommandCenter} />
      </FeatureFlagProvider>,
    );
    expect(screen.getByText("Location Overview")).toBeInTheDocument();
  });

  it("shows location names when the feature is enabled", () => {
    render(
      <FeatureFlagProvider flags={{ [MULTI_LOCATION_FEATURE]: true }}>
        <CommandCenterWidget data={sampleCommandCenter} />
      </FeatureFlagProvider>,
    );
    expect(screen.getByText("Downtown Branch")).toBeInTheDocument();
    expect(screen.getByText("Sunset District")).toBeInTheDocument();
  });

  it("shows roll-up KPI tiles when the feature is enabled", () => {
    render(
      <FeatureFlagProvider flags={{ [MULTI_LOCATION_FEATURE]: true }}>
        <CommandCenterWidget data={sampleCommandCenter} />
      </FeatureFlagProvider>,
    );
    expect(screen.getByText("Profile Views")).toBeInTheDocument();
    expect(screen.getByText("Calls")).toBeInTheDocument();
    expect(screen.getByText("Directions")).toBeInTheDocument();
  });

  it("is absent when flag is absent (fail-closed)", () => {
    render(
      <FeatureFlagProvider flags={{}}>
        <CommandCenterWidget data={sampleCommandCenter} />
      </FeatureFlagProvider>,
    );
    expect(screen.queryByText("Location Overview")).not.toBeInTheDocument();
  });
});
