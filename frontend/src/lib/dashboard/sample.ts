import type { HealthScore, PerformanceSummary } from "./types";

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
