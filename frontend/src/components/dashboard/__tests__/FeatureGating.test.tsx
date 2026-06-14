import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { describe, expect, it } from "vitest";

import {
  HEALTH_SCORE_FEATURE,
  HealthScoreWidget,
} from "@/components/dashboard/HealthScoreWidget";
import {
  PERFORMANCE_FEATURE,
  PerformanceWidget,
} from "@/components/dashboard/PerformanceWidget";
import {
  FeatureFlagProvider,
  type FeatureFlags,
} from "@/components/feature-flags/FeatureFlagProvider";
import { sampleHealthScore, samplePerformance } from "@/lib/dashboard/sample";

function renderWithFlags(ui: ReactElement, flags: FeatureFlags) {
  return render(<FeatureFlagProvider flags={flags}>{ui}</FeatureFlagProvider>);
}

describe("dashboard widget feature gating (PRD §7 D-6)", () => {
  it("hides the health-score widget when its feature flag is off", () => {
    renderWithFlags(<HealthScoreWidget data={sampleHealthScore} />, {
      [HEALTH_SCORE_FEATURE]: false,
    });
    expect(screen.queryByText("Profile Health")).not.toBeInTheDocument();
  });

  it("renders the health-score widget when its feature flag is on", () => {
    renderWithFlags(<HealthScoreWidget data={sampleHealthScore} />, {
      [HEALTH_SCORE_FEATURE]: true,
    });
    expect(screen.getByText("Profile Health")).toBeInTheDocument();
  });

  it("hides the performance widget when its flag is absent (fail-closed)", () => {
    // No flags at all — an unknown key must resolve OFF, never accidentally on.
    renderWithFlags(<PerformanceWidget data={samplePerformance} />, {});
    expect(screen.queryByText("Performance")).not.toBeInTheDocument();
  });

  it("renders the performance widget and its metrics when the flag is on", () => {
    renderWithFlags(<PerformanceWidget data={samplePerformance} />, {
      [PERFORMANCE_FEATURE]: true,
    });
    expect(screen.getByText("Performance")).toBeInTheDocument();
    expect(screen.getByText("Discovery searches")).toBeInTheDocument();
  });
});
