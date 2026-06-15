"use client";

import { useState } from "react";

import { FeatureGate } from "@/components/feature-flags/FeatureGate";
import { Card, CardHeader } from "@/components/ui/Card";
import { computeRollup, countByFilter, filterLocations, type HealthFilter } from "@/lib/dashboard/rollup";
import type { CommandCenterData } from "@/lib/dashboard/types";

import { CommandCenterMap } from "./CommandCenterMap";
import { LocationFilters } from "./LocationFilters";
import { RollupKPIGrid } from "./RollupKPIGrid";

/** Stable feature key gating this widget (PRD §7 D-6). */
export const MULTI_LOCATION_FEATURE = "dashboard_multi_location";

interface CommandCenterWidgetProps {
  data: CommandCenterData;
  /** Override the gating feature key (defaults to "dashboard_multi_location"). */
  feature?: string;
}

/**
 * Multi-location command center (PRD §7 D-3): map + filters + roll-up KPIs +
 * location list. Hidden entirely when its feature flag is off for the client (D-6).
 *
 * Filter changes recompute roll-ups client-side. The SVG map plots lat/lng
 * relative to the bounding box of the filtered set.
 */
export function CommandCenterWidget({
  data,
  feature = MULTI_LOCATION_FEATURE,
}: CommandCenterWidgetProps) {
  const [healthFilter, setHealthFilter] = useState<HealthFilter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const filtered = filterLocations(data.locations, healthFilter);
  const rollup = computeRollup(filtered);
  const counts = countByFilter(data.locations);

  function handleFilterChange(f: HealthFilter) {
    setHealthFilter(f);
    setSelectedId(null);
  }

  return (
    <FeatureGate feature={feature}>
      <div className="flex flex-col gap-6">
        <Card>
          <CardHeader
            title="Location Overview"
            subtitle={`${data.total_locations} location${data.total_locations !== 1 ? "s" : ""}`}
          />
          <div className="p-6 pt-4">
            <LocationFilters
              value={healthFilter}
              onChange={handleFilterChange}
              counts={counts}
            />
          </div>
        </Card>

        <RollupKPIGrid kpis={rollup} locationCount={filtered.length} />

        <CommandCenterMap
          locations={filtered}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />

        <Card>
          <CardHeader
            title="Locations"
            subtitle={`Showing ${filtered.length} of ${data.total_locations}`}
          />
          <div className="divide-y divide-hairline px-6 pb-6 pt-2">
            {filtered.length === 0 ? (
              <p className="py-4 text-sm text-muted">
                No locations match the current filter.
              </p>
            ) : (
              filtered.map((loc) => {
                const dotColor =
                  loc.health_score >= 80
                    ? "bg-green-500"
                    : loc.health_score >= 50
                      ? "bg-amber-500"
                      : "bg-red-500";
                const isSelected = loc.id === selectedId;
                return (
                  <button
                    key={loc.id}
                    type="button"
                    onClick={() =>
                      setSelectedId(isSelected ? null : loc.id)
                    }
                    className={`flex w-full items-center justify-between gap-4 py-3 text-left transition-colors hover:text-brand ${
                      isSelected ? "text-brand" : "text-foreground"
                    }`}
                  >
                    <span className="flex min-w-0 items-center gap-3">
                      <span
                        className={`h-2.5 w-2.5 shrink-0 rounded-full ${dotColor}`}
                        aria-hidden
                      />
                      <span className="truncate text-sm font-medium">
                        {loc.name}
                      </span>
                    </span>
                    <span className="shrink-0 text-sm font-semibold tabular-nums text-brand">
                      {loc.health_score}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </Card>
      </div>
    </FeatureGate>
  );
}
