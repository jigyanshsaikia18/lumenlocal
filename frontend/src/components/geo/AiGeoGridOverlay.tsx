"use client";

import { rankColorClass } from "@/lib/ranking/colors";
import type { AiGridCell, GeoAiScan } from "@/lib/geo/types";

interface AiGeoGridOverlayProps {
  scan: GeoAiScan;
  /** Size of each cell in px (default 48). */
  cellSize?: number;
}

/** Returns the cell at (row, col) or a stub (absent, no competitor data) if missing. */
function cellAt(cells: AiGridCell[], row: number, col: number): AiGridCell {
  return cells.find((c) => c.row === row && c.col === col) ?? { row, col, mentioned: false, prominence: null };
}

/**
 * AI geo-grid: an N×N grid colored by AI-mention prominence, the same scale
 * as the classic GeoGridHeatmap (green = prominent, red = buried, gray =
 * absent). Each cell also overlays the top competitor mentioned there, so an
 * agency can see — node by node — who the AI is citing instead of the
 * business (P2C-5's "competitor AI-share comparison shown on the grid").
 */
export function AiGeoGridOverlay({ scan, cellSize = 56 }: AiGeoGridOverlayProps) {
  const n = scan.grid_dimensions;
  const rows = Array.from({ length: n }, (_, i) => i);
  const cols = Array.from({ length: n }, (_, i) => i);

  return (
    <div>
      <div
        role="grid"
        aria-label={`AI visibility grid for "${scan.prompt}"`}
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
            const rankForColor = cell.mentioned ? cell.prominence : null;
            const { bg, text } = rankColorClass(rankForColor);
            const competitor = cell.top_competitor;
            const cellLabel = cell.mentioned ? `AI#${cell.prominence ?? "?"}` : "—";
            const ariaLabel = [
              `Row ${row + 1} col ${col + 1}`,
              cell.mentioned ? `mentioned at prominence ${cell.prominence ?? "unranked"}` : "not mentioned",
              competitor ? `top competitor ${competitor.name} at ${competitor.ai_share}% AI share` : null,
            ]
              .filter(Boolean)
              .join(", ");

            return (
              <div
                key={`${row}-${col}`}
                role="gridcell"
                aria-label={ariaLabel}
                data-mentioned={cell.mentioned}
                data-prominence={cell.prominence ?? "unranked"}
                className={`relative flex flex-col items-center justify-center rounded-md text-xs font-bold transition-opacity ${bg} ${text}`}
                style={{ width: cellSize, height: cellSize }}
              >
                <span>{cellLabel}</span>
                {competitor ? (
                  <span
                    data-testid="competitor-badge"
                    title={`${competitor.name} — ${competitor.ai_share}% AI share`}
                    className="mt-0.5 max-w-full truncate rounded bg-black/30 px-1 text-[9px] font-medium leading-tight"
                  >
                    {competitor.name.slice(0, 1)}·{competitor.ai_share}%
                  </span>
                ) : null}
              </div>
            );
          }),
        )}
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-muted">
        <span>SAIV: <strong className="text-foreground">{scan.saiv.toFixed(1)}%</strong></span>
        <span>{scan.prompt}</span>
        <span>{new Date(scan.run_at).toLocaleDateString()}</span>
      </div>
      <AiGeoGridLegend />
    </div>
  );
}

function AiGeoGridLegend() {
  const entries: Array<{ rank: number | null; label: string }> = [
    { rank: 1, label: "1st mention" },
    { rank: 2, label: "2nd–3rd" },
    { rank: 5, label: "4th–7th" },
    { rank: 9, label: "8th–10th" },
    { rank: 13, label: "buried (11th+)" },
    { rank: null, label: "not mentioned" },
  ];
  return (
    <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted">
      <div className="flex flex-wrap gap-2">
        {entries.map(({ rank, label }) => {
          const { bg } = rankColorClass(rank);
          return (
            <div key={label} className="flex items-center gap-1">
              <span className={`inline-block h-3 w-3 rounded-sm ${bg}`} />
              <span>{label}</span>
            </div>
          );
        })}
      </div>
      <div className="flex items-center gap-1">
        <span className="inline-block rounded bg-black/30 px-1 text-[9px] font-medium text-white">C·%</span>
        <span>top competitor &amp; AI share at that node</span>
      </div>
    </div>
  );
}
