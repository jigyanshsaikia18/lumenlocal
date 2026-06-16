import type {
  AiGridCell,
  CitedSource,
  GeoAiScan,
  GeoDashboardData,
  ProviderBreakdown,
  SAIVDataPoint,
} from "./types";

/** 5×5 AI grid fixture. Cells placed row-major (row 0..4, col 0..4). */
const cells5x5: AiGridCell[] = [
  // row 0 (top)
  { row: 0, col: 0, mentioned: false, prominence: null, top_competitor: { name: "Daily Grind Coffee", ai_share: 64 } },
  { row: 0, col: 1, mentioned: true, prominence: 4, top_competitor: { name: "Daily Grind Coffee", ai_share: 48 } },
  { row: 0, col: 2, mentioned: true, prominence: 2 },
  { row: 0, col: 3, mentioned: true, prominence: 5, top_competitor: { name: "Brew & Co.", ai_share: 40 } },
  { row: 0, col: 4, mentioned: false, prominence: null, top_competitor: { name: "Brew & Co.", ai_share: 71 } },
  // row 1
  { row: 1, col: 0, mentioned: true, prominence: 3 },
  { row: 1, col: 1, mentioned: true, prominence: 1 },
  { row: 1, col: 2, mentioned: true, prominence: 1 },
  { row: 1, col: 3, mentioned: true, prominence: 2 },
  { row: 1, col: 4, mentioned: true, prominence: 6, top_competitor: { name: "Brew & Co.", ai_share: 35 } },
  // row 2
  { row: 2, col: 0, mentioned: true, prominence: 4 },
  { row: 2, col: 1, mentioned: true, prominence: 1 },
  { row: 2, col: 2, mentioned: true, prominence: 1 },
  { row: 2, col: 3, mentioned: true, prominence: 2 },
  { row: 2, col: 4, mentioned: false, prominence: null, top_competitor: { name: "Brew & Co.", ai_share: 58 } },
  // row 3
  { row: 3, col: 0, mentioned: false, prominence: null, top_competitor: { name: "Daily Grind Coffee", ai_share: 52 } },
  { row: 3, col: 1, mentioned: true, prominence: 3 },
  { row: 3, col: 2, mentioned: true, prominence: 2 },
  { row: 3, col: 3, mentioned: true, prominence: 7, top_competitor: { name: "Brew & Co.", ai_share: 44 } },
  { row: 3, col: 4, mentioned: false, prominence: null, top_competitor: { name: "Brew & Co.", ai_share: 80 } },
  // row 4 (bottom)
  { row: 4, col: 0, mentioned: false, prominence: null, top_competitor: { name: "Daily Grind Coffee", ai_share: 69 } },
  { row: 4, col: 1, mentioned: false, prominence: null, top_competitor: { name: "Daily Grind Coffee", ai_share: 55 } },
  { row: 4, col: 2, mentioned: true, prominence: 8 },
  { row: 4, col: 3, mentioned: false, prominence: null, top_competitor: { name: "Brew & Co.", ai_share: 62 } },
  { row: 4, col: 4, mentioned: false, prominence: null, top_competitor: { name: "Brew & Co.", ai_share: 88 } },
];

export const sampleAiScan: GeoAiScan = {
  id: "ai-scan-fixture-01",
  location_id: "loc-1",
  prompt: "best coffee shop near me",
  grid_dimensions: 5,
  cells: cells5x5,
  saiv: 42.5,
  cited_sources: ["Yelp", "TripAdvisor", "Local Eats Blog", "Google Maps", "Reddit"],
  run_at: "2026-06-16T09:00:00Z",
};

const saiv_history: SAIVDataPoint[] = [
  { date: "2026-01-06", saiv: 18, prompt: "best coffee shop near me" },
  { date: "2026-01-13", saiv: 20, prompt: "best coffee shop near me" },
  { date: "2026-01-20", saiv: 22, prompt: "best coffee shop near me" },
  { date: "2026-01-27", saiv: 24, prompt: "best coffee shop near me" },
  { date: "2026-02-03", saiv: 26, prompt: "best coffee shop near me" },
  { date: "2026-02-10", saiv: 28, prompt: "best coffee shop near me" },
  { date: "2026-02-17", saiv: 25, prompt: "best coffee shop near me" },
  { date: "2026-02-24", saiv: 30, prompt: "best coffee shop near me" },
  { date: "2026-03-03", saiv: 32, prompt: "best coffee shop near me" },
  { date: "2026-03-10", saiv: 34, prompt: "best coffee shop near me" },
  { date: "2026-03-17", saiv: 31, prompt: "best coffee shop near me" },
  { date: "2026-03-24", saiv: 35, prompt: "best coffee shop near me" },
  { date: "2026-03-31", saiv: 37, prompt: "best coffee shop near me" },
  { date: "2026-04-07", saiv: 36, prompt: "best coffee shop near me" },
  { date: "2026-04-14", saiv: 38, prompt: "best coffee shop near me" },
  { date: "2026-04-21", saiv: 40, prompt: "best coffee shop near me" },
  { date: "2026-04-28", saiv: 39, prompt: "best coffee shop near me" },
  { date: "2026-05-05", saiv: 41, prompt: "best coffee shop near me" },
  { date: "2026-05-12", saiv: 44, prompt: "best coffee shop near me" },
  { date: "2026-05-19", saiv: 43, prompt: "best coffee shop near me" },
  { date: "2026-05-26", saiv: 45, prompt: "best coffee shop near me" },
  { date: "2026-06-02", saiv: 47, prompt: "best coffee shop near me" },
  { date: "2026-06-09", saiv: 40, prompt: "best coffee shop near me" },
  { date: "2026-06-16", saiv: 42.5, prompt: "best coffee shop near me" },
];

const provider_breakdown: ProviderBreakdown[] = [
  { provider: "ai_overviews", saiv: 55, mention_rate: 72 },
  { provider: "ai_mode", saiv: 48, mention_rate: 64 },
  { provider: "gemini", saiv: 40, mention_rate: 58 },
  { provider: "chatgpt", saiv: 36, mention_rate: 50 },
  { provider: "perplexity", saiv: 44, mention_rate: 60 },
  { provider: "grok", saiv: 28, mention_rate: 38 },
];

const cited_sources: CitedSource[] = [
  { source: "Yelp", citations: 19 },
  { source: "Google Maps", citations: 16 },
  { source: "TripAdvisor", citations: 11 },
  { source: "Local Eats Blog", citations: 7 },
  { source: "Reddit", citations: 4 },
];

export const sampleGeoDashboard: GeoDashboardData = {
  location_id: "loc-1",
  location_name: "Downtown Branch",
  latest_scan: sampleAiScan,
  saiv_history,
  provider_breakdown,
  cited_sources,
};
