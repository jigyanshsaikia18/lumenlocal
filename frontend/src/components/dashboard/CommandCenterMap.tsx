"use client";

import { healthStatus } from "@/lib/dashboard/rollup";
import type { LocationSummary } from "@/lib/dashboard/types";

const STATUS_COLOR: Record<"good" | "warning" | "critical", string> = {
  good: "#22c55e",
  warning: "#f59e0b",
  critical: "#ef4444",
};

const SVG_W = 560;
const SVG_H = 280;
const PAD = 36;

interface CommandCenterMapProps {
  locations: LocationSummary[];
  selectedId?: string | null;
  onSelect?: (id: string) => void;
}

/**
 * SVG-based relative-position map (PRD §7 D-3). Normalises lat/lng to SVG
 * coordinates within the bounding box of the filtered location set. Dots are
 * colour-coded by health status. No external tile service is required.
 */
export function CommandCenterMap({
  locations,
  selectedId,
  onSelect,
}: CommandCenterMapProps) {
  const withCoords = locations.filter(
    (l) => l.latitude !== null && l.longitude !== null,
  );

  if (withCoords.length === 0) {
    return (
      <div
        aria-label="Location map"
        className="flex h-48 items-center justify-center rounded-2xl border border-hairline bg-canvas/40 text-sm text-muted"
      >
        No location coordinates available
      </div>
    );
  }

  const lats = withCoords.map((l) => l.latitude as number);
  const lngs = withCoords.map((l) => l.longitude as number);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  const latRange = maxLat - minLat || 1;
  const lngRange = maxLng - minLng || 1;
  const innerW = SVG_W - PAD * 2;
  const innerH = SVG_H - PAD * 2;

  function toSvg(lat: number, lng: number) {
    return {
      x: PAD + ((lng - minLng) / lngRange) * innerW,
      y: PAD + ((maxLat - lat) / latRange) * innerH, // flip Y: north is up
    };
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-hairline bg-canvas/40">
      <svg
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        className="h-auto w-full"
        role="img"
        aria-label="Location map"
      >
        {/* subtle grid lines */}
        {[0, 1, 2, 3, 4].map((i) => (
          <line
            key={i}
            x1={PAD}
            y1={PAD + (i / 4) * innerH}
            x2={SVG_W - PAD}
            y2={PAD + (i / 4) * innerH}
            stroke="currentColor"
            strokeOpacity="0.07"
            strokeWidth="1"
          />
        ))}

        {withCoords.map((loc) => {
          const { x, y } = toSvg(loc.latitude as number, loc.longitude as number);
          const color = STATUS_COLOR[healthStatus(loc.health_score)];
          const selected = loc.id === selectedId;
          return (
            <g
              key={loc.id}
              onClick={() => onSelect?.(loc.id)}
              className="cursor-pointer"
              role="button"
              aria-label={loc.name}
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && onSelect?.(loc.id)}
            >
              {selected && (
                <circle cx={x} cy={y} r={18} fill={color} fillOpacity="0.18" />
              )}
              <circle
                cx={x}
                cy={y}
                r={selected ? 9 : 6}
                fill={color}
                stroke="white"
                strokeWidth={selected ? 2.5 : 1.5}
              />
            </g>
          );
        })}
      </svg>

      <div className="flex gap-4 px-4 pb-3">
        {(["good", "warning", "critical"] as const).map((s) => (
          <span key={s} className="flex items-center gap-1.5 text-xs text-muted">
            <span
              className="inline-block h-2 w-2 shrink-0 rounded-full"
              style={{ background: STATUS_COLOR[s] }}
            />
            {s === "good" ? "≥ 80" : s === "warning" ? "50 – 79" : "< 50"}
          </span>
        ))}
      </div>
    </div>
  );
}
