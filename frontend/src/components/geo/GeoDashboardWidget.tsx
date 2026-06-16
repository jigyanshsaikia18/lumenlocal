"use client";

import { Card, CardHeader } from "@/components/ui/Card";
import { FeatureGate } from "@/components/feature-flags/FeatureGate";
import type { GeoDashboardData } from "@/lib/geo/types";

import { AiGeoGridOverlay } from "./AiGeoGridOverlay";
import { CitedSourcesList } from "./CitedSourcesList";
import { ProviderBreakdownChart } from "./ProviderBreakdownChart";
import { SAIVHistoryChart } from "./SAIVHistoryChart";

export const GEO_DASHBOARD_FEATURE = "geo_dashboard";

interface GeoDashboardWidgetProps {
  data: GeoDashboardData;
  feature?: string;
}

/**
 * P2C-5 — GEO dashboard widget.
 * Combines the SAIV trend, per-provider breakdown, cited sources, and the
 * AI geo-grid with its competitor AI-share overlay into one view.
 * Gated by the "geo_dashboard" feature flag (PRD §7).
 */
export function GeoDashboardWidget({
  data,
  feature = GEO_DASHBOARD_FEATURE,
}: GeoDashboardWidgetProps) {
  const { latest_scan, saiv_history, provider_breakdown, cited_sources, location_name } = data;

  return (
    <FeatureGate feature={feature}>
      <div className="flex flex-col gap-6">
        <Card>
          <CardHeader title="SAIV Trend" subtitle="AI-Search Visibility over time" />
          <div className="p-6 pt-2">
            <SAIVHistoryChart data={saiv_history} />
          </div>
        </Card>

        <Card>
          <CardHeader
            title="AI Geo-Grid"
            subtitle={`${location_name} · ${latest_scan.prompt} · competitor AI-share overlay`}
          />
          <div className="overflow-x-auto p-6 pt-4">
            <AiGeoGridOverlay scan={latest_scan} />
          </div>
        </Card>

        <Card>
          <CardHeader title="Per-Provider Breakdown" subtitle="SAIV by AI surface" />
          <div className="p-6 pt-2">
            <ProviderBreakdownChart data={provider_breakdown} />
          </div>
        </Card>

        <Card>
          <CardHeader title="Cited Sources" subtitle="Third-party sources the AI referenced" />
          <div className="p-6 pt-4">
            <CitedSourcesList sources={cited_sources} />
          </div>
        </Card>
      </div>
    </FeatureGate>
  );
}
