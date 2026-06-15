import type { CommandCenterData, HealthScore, PerformanceSummary } from "./types";

/**
 * Illustrative dashboard data for the demo route and tests. Real values come from
 * `GET /locations/{id}/health-score` and `GET /locations/{id}/performance`.
 */
export const sampleHealthScore: HealthScore = {
  score: 82,
  grade: "B",
  completeness: 88,
  gaps: [
    { id: "services", label: "Add 3 missing services", impact: 6, severity: "high" },
    { id: "photos", label: "Upload recent storefront photos", impact: 5, severity: "medium" },
    { id: "qa", label: "Answer 4 open customer questions", impact: 4, severity: "medium" },
    { id: "attributes", label: "Set 2 business attributes", impact: 3, severity: "low" },
  ],
};

export const samplePerformance: PerformanceSummary = {
  period: { from: "2026-05-15", to: "2026-06-13" },
  comparisonPeriod: { from: "2026-04-15", to: "2026-05-14" },
  metrics: [
    { key: "views", label: "Profile views", value: 12480, previousValue: 11020 },
    { key: "searches_branded", label: "Branded searches", value: 3420, previousValue: 3510 },
    { key: "searches_discovery", label: "Discovery searches", value: 8160, previousValue: 6890 },
    { key: "calls", label: "Calls", value: 286, previousValue: 254 },
    { key: "website_clicks", label: "Website clicks", value: 1740, previousValue: 1740 },
    { key: "directions", label: "Direction requests", value: 932, previousValue: 1012 },
  ],
};

// ---------------------------------------------------------------------------
// Command center sample data (P1E-2 — multi-location roll-up)
// Rollup sums: views 24980, calls 596, directions 1340, website_clicks 1860
// Health breakdown: 1 good (≥80), 2 warning (50-79), 2 critical (<50)
// ---------------------------------------------------------------------------
export const sampleCommandCenter: CommandCenterData = {
  client_id: "c0000000-0000-0000-0000-000000000001",
  total_locations: 5,
  rollup: { views: 24980, calls: 596, directions: 1340, website_clicks: 1860 },
  locations: [
    {
      id: "loc-1",
      name: "Downtown Branch",
      latitude: 37.7849,
      longitude: -122.4094,
      health_score: 88,
      kpis: { views: 7200, calls: 180, directions: 420, website_clicks: 560 },
    },
    {
      id: "loc-2",
      name: "Mission District",
      latitude: 37.7599,
      longitude: -122.4148,
      health_score: 74,
      kpis: { views: 5400, calls: 140, directions: 280, website_clicks: 380 },
    },
    {
      id: "loc-3",
      name: "SoMa Office",
      latitude: 37.7785,
      longitude: -122.3948,
      health_score: 61,
      kpis: { views: 4100, calls: 102, directions: 210, website_clicks: 280 },
    },
    {
      id: "loc-4",
      name: "Nob Hill",
      latitude: 37.7935,
      longitude: -122.4146,
      health_score: 42,
      kpis: { views: 5080, calls: 110, directions: 285, website_clicks: 390 },
    },
    {
      id: "loc-5",
      name: "Sunset District",
      latitude: 37.7597,
      longitude: -122.4785,
      health_score: 33,
      kpis: { views: 3200, calls: 64, directions: 145, website_clicks: 250 },
    },
  ],
};
