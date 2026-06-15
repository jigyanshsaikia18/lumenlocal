import type { LocationKPIs } from "@/lib/dashboard/types";

const KPI_DEFS: { key: keyof LocationKPIs; label: string }[] = [
  { key: "views", label: "Profile Views" },
  { key: "calls", label: "Calls" },
  { key: "directions", label: "Directions" },
  { key: "website_clicks", label: "Website Clicks" },
];

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString("en-US");
}

interface RollupKPIGridProps {
  kpis: LocationKPIs;
  locationCount: number;
}

/** Aggregated KPI tiles — the roll-up cards across all filtered locations (PRD §7 D-3). */
export function RollupKPIGrid({ kpis, locationCount }: RollupKPIGridProps) {
  const suffix = `across ${locationCount} location${locationCount !== 1 ? "s" : ""}`;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {KPI_DEFS.map(({ key, label }) => (
        <div
          key={key}
          className="rounded-2xl border border-hairline bg-surface p-4 shadow-card"
        >
          <p className="text-xs font-medium text-muted">{label}</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">
            {fmt(kpis[key])}
          </p>
          <p className="mt-0.5 text-xs text-muted">{suffix}</p>
        </div>
      ))}
    </div>
  );
}
