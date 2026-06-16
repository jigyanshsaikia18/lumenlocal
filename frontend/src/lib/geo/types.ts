/**
 * GEO dashboard data contracts for P2C-5 (SAIV trend, provider breakdown,
 * cited sources, competitor AI-share comparison on the grid).
 * Mirrors `geo_ai_scans` / `competitors` columns from 04_Database_Schema.md §6
 * and the normalized `AiVisibilityRecord` from backend/app/geo/ai/records.py.
 */

/** The AI surfaces tracked for visibility (PRD GEO-2). Matches the backend `Provider` enum. */
export type AiProvider =
  | "ai_overviews"
  | "ai_mode"
  | "gemini"
  | "chatgpt"
  | "perplexity"
  | "grok";

export const AI_PROVIDER_LABELS: Record<AiProvider, string> = {
  ai_overviews: "AI Overviews",
  ai_mode: "AI Mode",
  gemini: "Gemini",
  chatgpt: "ChatGPT",
  perplexity: "Perplexity",
  grok: "Grok",
};

/** A competitor's mention share at a grid node or across a whole scan. */
export interface CompetitorAiShare {
  name: string;
  /** % of sampled nodes/runs in which this competitor was mentioned (0-100). */
  ai_share: number;
}

/** One cell in the AI geo-grid matrix. Mirrors `GridCell` from lib/ranking/types. */
export interface AiGridCell {
  row: number;
  col: number;
  /** Was the tracked business mentioned by the AI at this node. */
  mentioned: boolean;
  /** 1-based pseudo-rank / order of mention. null when absent or buried. */
  prominence: number | null;
  latitude?: number;
  longitude?: number;
  /** The most-mentioned competitor at this node, for the AI-share overlay. */
  top_competitor?: CompetitorAiShare;
}

/** Full AI-search scan result for one prompt at one location. */
export interface GeoAiScan {
  id: string;
  location_id: string;
  prompt: string;
  /** Square grid side length (3, 5, 7, 9, 10). */
  grid_dimensions: number;
  /** Flattened grid — length = grid_dimensions². */
  cells: AiGridCell[];
  /** AI-Search Visibility score (0-100). */
  saiv: number;
  /** Third-party sources the AI referenced (GEO-5). */
  cited_sources: string[];
  run_at: string; // ISO-8601
}

/** One point on the SAIV history chart. */
export interface SAIVDataPoint {
  /** ISO date string (YYYY-MM-DD). */
  date: string;
  /** AI-Search Visibility (0-100). */
  saiv: number;
  prompt?: string;
}

/** SAIV + mention rate for a single provider, for the breakdown chart. */
export interface ProviderBreakdown {
  provider: AiProvider;
  saiv: number;
  /** % of sampled prompts where the business was mentioned at all (0-100). */
  mention_rate: number;
}

/** A source the AI cited, with how often it showed up across the scan. */
export interface CitedSource {
  source: string;
  citations: number;
}

/** Aggregated data fed to the GeoDashboardWidget. */
export interface GeoDashboardData {
  location_id: string;
  location_name: string;
  /** Most recent AI scan — drives the grid overlay. */
  latest_scan: GeoAiScan;
  /** Chronological history of SAIV values for the trend chart. */
  saiv_history: SAIVDataPoint[];
  provider_breakdown: ProviderBreakdown[];
  cited_sources: CitedSource[];
}
