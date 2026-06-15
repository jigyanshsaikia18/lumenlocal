"use client";

import type { HealthFilter } from "@/lib/dashboard/rollup";

const FILTERS: { key: HealthFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "good", label: "Good (≥ 80)" },
  { key: "warning", label: "Warning (50–79)" },
  { key: "critical", label: "Critical (< 50)" },
];

interface LocationFiltersProps {
  value: HealthFilter;
  onChange: (filter: HealthFilter) => void;
  /** Pre-computed location count for each bucket (including "all"). */
  counts: Record<HealthFilter, number>;
}

/** Health-score filter pills for the multi-location command center (PRD §7 D-3). */
export function LocationFilters({ value, onChange, counts }: LocationFiltersProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {FILTERS.map(({ key, label }) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange(key)}
          className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
            value === key
              ? "bg-brand text-white"
              : "border border-hairline bg-canvas/40 text-muted hover:border-brand/40 hover:text-foreground"
          }`}
        >
          {label}
          <span className="ml-1.5 tabular-nums opacity-70">({counts[key]})</span>
        </button>
      ))}
    </div>
  );
}
