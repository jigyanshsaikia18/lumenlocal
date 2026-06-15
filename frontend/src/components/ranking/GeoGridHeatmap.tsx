"use client";

import { rankColorClass } from "@/lib/ranking/colors";
import type { GeoGridScan, GridCell } from "@/lib/ranking/types";

interface GeoGridHeatmapProps {
  scan: GeoGridScan;
  /** Size of each cell in px (default 48). */
  cellSize?: number;
}

/** Returns the cell at (row, col) or a stub with null rank if missing. */
function cellAt(cells: GridCell[], row: number, col: number): GridCell {
  return cells.find((c) => c.row === row && c.col === col) ?? { row, col, rank: null };
}

/**
 * Geo-grid heatmap: an N×N grid of squares colored by local map-pack rank.
 * Green = top ranking, red = lower rank, gray = unranked.
 * No external chart library — pure CSS grid + Tailwind.
 */
export function GeoGridHeatmap({ scan, cellSize = 48 }: GeoGridHeatmapProps) {
  const n = scan.grid_dimensions;
  const rows = Array.from({ length: n }, (_, i) => i);
  const cols = Array.from({ length: n }, (_, i) => i);

  return (
    <div>
      <div
        role="grid"
        aria-label={`Geo-grid heatmap for "${scan.search_term}"`}
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${n}, ${cellSize}px)`,
          gridTemplateRows: `repeat(${n}, ${cellSize}px)`,
          gap: "4px",
        }}
      >
        {rows.map((row) =>
          cols.map((col) => {
            const cell = cellAt(scan.cells, row, col);
            const { bg, text, label } = rankColorClass(cell.rank);
            return (
              <div
                key={`${row}-${col}`}
                role="gridcell"
                aria-label={
                  cell.rank !== null
                    ? `Row ${row + 1} col ${col + 1}: rank ${cell.rank}`
                    : `Row ${row + 1} col ${col + 1}: unranked`
                }
                data-rank={cell.rank ?? "unranked"}
                className={`flex items-center justify-center rounded-md text-xs font-bold transition-opacity ${bg} ${text}`}
                style={{ width: cellSize, height: cellSize }}
                title={label}
              >
                {label}
              </div>
            );
          }),
        )}
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-muted">
        <span>SoLV: <strong className="text-foreground">{scan.solv.toFixed(1)}%</strong></span>
        <span>{scan.search_term}</span>
        <span>{new Date(scan.run_at).toLocaleDateString()}</span>
      </div>
      <GeoGridLegend />
    </div>
  );
}

function GeoGridLegend() {
  const entries: Array<{ rank: number | null; label: string }> = [
    { rank: 1, label: "#1" },
    { rank: 2, label: "#2–3" },
    { rank: 5, label: "#4–7" },
    { rank: 9, label: "#8–10" },
    { rank: 13, label: "#11–15" },
    { rank: 18, label: "#16–20" },
    { rank: null, label: "20+" },
  ];
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {entries.map(({ rank, label }) => {
        const { bg } = rankColorClass(rank);
        return (
          <div key={label} className="flex items-center gap-1">
            <span className={`inline-block h-3 w-3 rounded-sm ${bg}`} />
            <span className="text-xs text-muted">{label}</span>
          </div>
        );
      })}
    </div>
  );
}
