"use client";

import { Card, CardHeader } from "@/components/ui/Card";
import { FeatureGate } from "@/components/feature-flags/FeatureGate";
import type { RankTrendData } from "@/lib/ranking/types";

import { GeoGridHeatmap } from "./GeoGridHeatmap";
import { SoLVHistoryChart } from "./SoLVHistoryChart";

export const RANK_TRACKER_FEATURE = "rank_tracker";

interface RankTrackerWidgetProps {
  data: RankTrendData;
  feature?: string;
}

/**
 * P2B-3 — Rank Trend + Heatmap widget.
 * Combines the geo-grid heatmap with a SoLV history line chart.
 * Gated by the "rank_tracker" feature flag (PRD §7).
 */
export function RankTrackerWidget({
  data,
  feature = RANK_TRACKER_FEATURE,
}: RankTrackerWidgetProps) {
  const { latest_scan, solv_history, location_name } = data;

  return (
    <FeatureGate feature={feature}>
      <div className="flex flex-col gap-6">
        <Card>
          <CardHeader
            title="Geo-Grid Heatmap"
            subtitle={`${location_name} · ${latest_scan.search_term}`}
          />
          <div className="overflow-x-auto p-6 pt-4">
            <GeoGridHeatmap scan={latest_scan} />
          </div>
        </Card>

        <Card>
          <CardHeader
            title="SoLV Trend"
            subtitle="Share of Local Voice over time"
          />
          <div className="p-6 pt-2">
            <SoLVHistoryChart data={solv_history} />
          </div>
        </Card>
      </div>
    </FeatureGate>
  );
}
