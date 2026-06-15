import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GeoGridHeatmap } from "@/components/ranking/GeoGridHeatmap";
import { rankColorClass } from "@/lib/ranking/colors";
import { sampleScan } from "@/lib/ranking/sample";
import type { GeoGridScan } from "@/lib/ranking/types";

// ---------------------------------------------------------------------------
// Pure utility: rankColorClass
// ---------------------------------------------------------------------------

describe("rankColorClass", () => {
  it("returns green-600 bg for rank #1", () => {
    expect(rankColorClass(1).bg).toBe("bg-green-600");
  });

  it("returns green-400 bg for rank #2", () => {
    expect(rankColorClass(2).bg).toBe("bg-green-400");
  });

  it("returns green-400 bg for rank #3", () => {
    expect(rankColorClass(3).bg).toBe("bg-green-400");
  });

  it("returns amber-400 bg for rank #4", () => {
    expect(rankColorClass(4).bg).toBe("bg-amber-400");
  });

  it("returns amber-400 bg for rank #7", () => {
    expect(rankColorClass(7).bg).toBe("bg-amber-400");
  });

  it("returns orange-500 bg for rank #8", () => {
    expect(rankColorClass(8).bg).toBe("bg-orange-500");
  });

  it("returns orange-500 bg for rank #10", () => {
    expect(rankColorClass(10).bg).toBe("bg-orange-500");
  });

  it("returns red-400 bg for rank #11", () => {
    expect(rankColorClass(11).bg).toBe("bg-red-400");
  });

  it("returns red-700 bg for rank #16", () => {
    expect(rankColorClass(16).bg).toBe("bg-red-700");
  });

  it("returns gray-100 bg for null rank (unranked)", () => {
    expect(rankColorClass(null).bg).toBe("bg-gray-100");
  });

  it("returns gray-100 bg for rank 21 (beyond top-20)", () => {
    expect(rankColorClass(21).bg).toBe("bg-gray-100");
  });

  it('returns label "unranked" for null', () => {
    expect(rankColorClass(null).label).toBe("unranked");
  });

  it("returns white text for rank #1", () => {
    expect(rankColorClass(1).text).toBe("text-white");
  });
});

// ---------------------------------------------------------------------------
// Component: GeoGridHeatmap renders grid from fixture data
// ---------------------------------------------------------------------------

describe("GeoGridHeatmap", () => {
  it("renders a grid with aria role=grid", () => {
    render(<GeoGridHeatmap scan={sampleScan} />);
    expect(screen.getByRole("grid")).toBeInTheDocument();
  });

  it("renders grid_dimensions² cells", () => {
    render(<GeoGridHeatmap scan={sampleScan} />);
    const cells = screen.getAllByRole("gridcell");
    expect(cells).toHaveLength(sampleScan.grid_dimensions ** 2);
  });

  it("labels rank-1 cells as rank 1", () => {
    render(<GeoGridHeatmap scan={sampleScan} />);
    const rankOneCells = screen
      .getAllByRole("gridcell")
      .filter((el) => el.dataset.rank === "1");
    // fixture has 4 rank-1 cells: (1,1), (1,2), (2,1), (2,2)
    expect(rankOneCells).toHaveLength(4);
  });

  it("applies green-600 bg class to rank-1 cells", () => {
    render(<GeoGridHeatmap scan={sampleScan} />);
    const rankOneCells = screen
      .getAllByRole("gridcell")
      .filter((el) => el.dataset.rank === "1");
    for (const cell of rankOneCells) {
      expect(cell.className).toContain("bg-green-600");
    }
  });

  it("applies gray-100 bg class to the unranked cell", () => {
    render(<GeoGridHeatmap scan={sampleScan} />);
    const unrankedCells = screen
      .getAllByRole("gridcell")
      .filter((el) => el.dataset.rank === "unranked");
    expect(unrankedCells).toHaveLength(1);
    expect(unrankedCells[0].className).toContain("bg-gray-100");
  });

  it("renders SoLV value in the summary row", () => {
    render(<GeoGridHeatmap scan={sampleScan} />);
    expect(screen.getByText(/16\.0%/)).toBeInTheDocument();
  });

  it("renders the search term in the summary row", () => {
    render(<GeoGridHeatmap scan={sampleScan} />);
    expect(screen.getByText(sampleScan.search_term)).toBeInTheDocument();
  });

  it("accepts a custom cellSize without crashing", () => {
    render(<GeoGridHeatmap scan={sampleScan} cellSize={32} />);
    expect(screen.getByRole("grid")).toBeInTheDocument();
  });

  it("renders correct grid label with search term", () => {
    render(<GeoGridHeatmap scan={sampleScan} />);
    expect(
      screen.getByRole("grid", {
        name: `Geo-grid heatmap for "${sampleScan.search_term}"`,
      }),
    ).toBeInTheDocument();
  });

  it("handles a 3×3 scan without crashing", () => {
    const smallScan: GeoGridScan = {
      id: "scan-3x3",
      location_id: "loc-test",
      search_term: "pizza near me",
      grid_dimensions: 3,
      cells: [
        { row: 0, col: 0, rank: 1 },
        { row: 0, col: 1, rank: 3 },
        { row: 0, col: 2, rank: 5 },
        { row: 1, col: 0, rank: 2 },
        { row: 1, col: 1, rank: 1 },
        { row: 1, col: 2, rank: 7 },
        { row: 2, col: 0, rank: 9 },
        { row: 2, col: 1, rank: null },
        { row: 2, col: 2, rank: null },
      ],
      solv: 22.2,
      run_at: "2026-06-10T08:00:00Z",
    };
    render(<GeoGridHeatmap scan={smallScan} />);
    const cells = screen.getAllByRole("gridcell");
    expect(cells).toHaveLength(9);
  });

  it("fills missing cells with unranked gray", () => {
    const sparseGridScan: GeoGridScan = {
      id: "scan-sparse",
      location_id: "loc-test",
      search_term: "dentist near me",
      grid_dimensions: 3,
      cells: [{ row: 0, col: 0, rank: 1 }], // only one cell provided
      solv: 11.1,
      run_at: "2026-06-01T00:00:00Z",
    };
    render(<GeoGridHeatmap scan={sparseGridScan} />);
    const cells = screen.getAllByRole("gridcell");
    expect(cells).toHaveLength(9);
    const unranked = cells.filter((c) => c.dataset.rank === "unranked");
    // 8 missing cells + 0 explicitly null = 8 unranked
    expect(unranked).toHaveLength(8);
  });
});
