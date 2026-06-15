/**
 * Rank-tracking data contracts for P2B-3 (geo-grid heatmap + SoLV trend).
 * Mirrors `geogrid_scans` columns from 04_Database_Schema.md §5.
 */

/** One cell in the geo-grid matrix. null rank = outside top-20 / unranked. */
export interface GridCell {
  row: number;
  col: number;
  rank: number | null;
  /** Approximate lat/lng of the grid node (informational). */
  latitude?: number;
  longitude?: number;
  /** Top competitors at this node (optional preview). */
  competitors?: string[];
}

/** Full scan result for one keyword at one location. */
export interface GeoGridScan {
  id: string;
  location_id: string;
  search_term: string;
  /** Square grid side length (3, 5, 7, 9, 10). */
  grid_dimensions: number;
  /** Flattened grid — length = grid_dimensions². */
  cells: GridCell[];
  /** Share of Local Voice: % of cells where the business ranks #1. */
  solv: number;
  run_at: string; // ISO-8601
}

/** One point on the SoLV history chart. */
export interface SoLVDataPoint {
  /** ISO date string (YYYY-MM-DD). */
  date: string;
  /** Share of Local Voice (0–100). */
  solv: number;
  /** Keyword label for tooltip context. */
  search_term?: string;
}

/** Aggregated data fed to the RankTrackerWidget. */
export interface RankTrendData {
  location_id: string;
  location_name: string;
  /** Most recent scan — drives the heatmap. */
  latest_scan: GeoGridScan;
  /** Chronological history of SoLV values for the trend chart. */
  solv_history: SoLVDataPoint[];
}
