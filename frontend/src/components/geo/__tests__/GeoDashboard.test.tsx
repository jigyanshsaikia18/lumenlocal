import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AiGeoGridOverlay } from "@/components/geo/AiGeoGridOverlay";
import { SAIVHistoryChart } from "@/components/geo/SAIVHistoryChart";
import { sampleAiScan, sampleGeoDashboard } from "@/lib/geo/sample";
import type { GeoAiScan } from "@/lib/geo/types";

// ---------------------------------------------------------------------------
// SAIVHistoryChart — SAIV trend
// ---------------------------------------------------------------------------

describe("SAIVHistoryChart", () => {
  it("renders a line chart for the SAIV history fixture", () => {
    const { container } = render(<SAIVHistoryChart data={sampleGeoDashboard.saiv_history} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
    expect(container.querySelectorAll("path.recharts-line-curve")).toHaveLength(1);
  });

  it("plots one point per fixture data point", () => {
    const { container } = render(<SAIVHistoryChart data={sampleGeoDashboard.saiv_history} />);
    const path = container.querySelector("path.recharts-line-curve");
    // One initial "M" plus one "C" curve segment per subsequent point.
    const segments = path?.getAttribute("d")?.match(/[MC]/g) ?? [];
    expect(segments).toHaveLength(sampleGeoDashboard.saiv_history.length);
  });
});

// ---------------------------------------------------------------------------
// AiGeoGridOverlay — competitor AI-share overlay shown on the grid
// ---------------------------------------------------------------------------

describe("AiGeoGridOverlay", () => {
  it("renders a grid with aria role=grid", () => {
    render(<AiGeoGridOverlay scan={sampleAiScan} />);
    expect(screen.getByRole("grid")).toBeInTheDocument();
  });

  it("renders grid_dimensions² cells", () => {
    render(<AiGeoGridOverlay scan={sampleAiScan} />);
    expect(screen.getAllByRole("gridcell")).toHaveLength(sampleAiScan.grid_dimensions ** 2);
  });

  it("marks mentioned vs unmentioned cells via data-mentioned", () => {
    render(<AiGeoGridOverlay scan={sampleAiScan} />);
    const cells = screen.getAllByRole("gridcell");
    const mentioned = cells.filter((c) => c.dataset.mentioned === "true");
    const expectedMentioned = sampleAiScan.cells.filter((c) => c.mentioned).length;
    expect(mentioned).toHaveLength(expectedMentioned);
  });

  it("renders a competitor overlay badge for every cell with a top_competitor", () => {
    render(<AiGeoGridOverlay scan={sampleAiScan} />);
    const badges = screen.getAllByTestId("competitor-badge");
    const expectedBadges = sampleAiScan.cells.filter((c) => c.top_competitor).length;
    expect(badges).toHaveLength(expectedBadges);
  });

  it("shows the competitor name and AI share in the badge title", () => {
    render(<AiGeoGridOverlay scan={sampleAiScan} />);
    const cell = sampleAiScan.cells.find((c) => c.top_competitor);
    expect(cell?.top_competitor).toBeDefined();
    const expectedTitle = `${cell!.top_competitor!.name} — ${cell!.top_competitor!.ai_share}% AI share`;
    expect(screen.getByTitle(expectedTitle)).toBeInTheDocument();
  });

  it("renders no competitor badge for a fully-mentioned cell", () => {
    render(<AiGeoGridOverlay scan={sampleAiScan} />);
    const cells = screen.getAllByRole("gridcell");
    const topRankCell = cells.find((c) => c.dataset.prominence === "1");
    expect(topRankCell).toBeDefined();
    expect(within(topRankCell!).queryByTestId("competitor-badge")).not.toBeInTheDocument();
  });

  it("renders the SAIV value and prompt in the summary row", () => {
    render(<AiGeoGridOverlay scan={sampleAiScan} />);
    expect(screen.getByText(/42\.5%/)).toBeInTheDocument();
    expect(screen.getByText(sampleAiScan.prompt)).toBeInTheDocument();
  });

  it("fills missing cells as unmentioned with no competitor data", () => {
    const sparseScan: GeoAiScan = {
      id: "ai-scan-sparse",
      location_id: "loc-test",
      prompt: "best dentist near me",
      grid_dimensions: 3,
      cells: [{ row: 0, col: 0, mentioned: true, prominence: 1 }],
      saiv: 11.1,
      cited_sources: [],
      run_at: "2026-06-01T00:00:00Z",
    };
    render(<AiGeoGridOverlay scan={sparseScan} />);
    const cells = screen.getAllByRole("gridcell");
    expect(cells).toHaveLength(9);
    const unmentioned = cells.filter((c) => c.dataset.mentioned === "false");
    expect(unmentioned).toHaveLength(8);
    expect(screen.queryAllByTestId("competitor-badge")).toHaveLength(0);
  });
});
