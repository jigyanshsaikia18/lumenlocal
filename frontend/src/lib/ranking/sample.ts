import type { GridCell, GeoGridScan, RankTrendData, SoLVDataPoint } from "./types";

/** 5×5 grid fixture. Cells placed row-major (row 0..4, col 0..4). */
const cells5x5: GridCell[] = [
  // row 0 (top)
  { row: 0, col: 0, rank: 4 },
  { row: 0, col: 1, rank: 3 },
  { row: 0, col: 2, rank: 2 },
  { row: 0, col: 3, rank: 5 },
  { row: 0, col: 4, rank: 8 },
  // row 1
  { row: 1, col: 0, rank: 3 },
  { row: 1, col: 1, rank: 1 },
  { row: 1, col: 2, rank: 1 },
  { row: 1, col: 3, rank: 3 },
  { row: 1, col: 4, rank: 7 },
  // row 2
  { row: 2, col: 0, rank: 5 },
  { row: 2, col: 1, rank: 1 },
  { row: 2, col: 2, rank: 1 },
  { row: 2, col: 3, rank: 2 },
  { row: 2, col: 4, rank: 9 },
  // row 3
  { row: 3, col: 0, rank: 8 },
  { row: 3, col: 1, rank: 4 },
  { row: 3, col: 2, rank: 3 },
  { row: 3, col: 3, rank: 6 },
  { row: 3, col: 4, rank: 11 },
  // row 4 (bottom)
  { row: 4, col: 0, rank: 13 },
  { row: 4, col: 1, rank: 10 },
  { row: 4, col: 2, rank: 7 },
  { row: 4, col: 3, rank: 12 },
  { row: 4, col: 4, rank: null },
];

/** SoLV = 4/25 = 16% — cells at (1,1), (1,2), (2,1), (2,2) are rank #1. */
export const sampleScan: GeoGridScan = {
  id: "scan-fixture-01",
  location_id: "loc-1",
  search_term: "coffee shop near me",
  grid_dimensions: 5,
  cells: cells5x5,
  solv: 16.0,
  run_at: "2026-06-16T09:00:00Z",
};

const solv_history: SoLVDataPoint[] = [
  { date: "2026-01-06", solv: 8, search_term: "coffee shop near me" },
  { date: "2026-01-13", solv: 8, search_term: "coffee shop near me" },
  { date: "2026-01-20", solv: 12, search_term: "coffee shop near me" },
  { date: "2026-01-27", solv: 12, search_term: "coffee shop near me" },
  { date: "2026-02-03", solv: 16, search_term: "coffee shop near me" },
  { date: "2026-02-10", solv: 20, search_term: "coffee shop near me" },
  { date: "2026-02-17", solv: 16, search_term: "coffee shop near me" },
  { date: "2026-02-24", solv: 20, search_term: "coffee shop near me" },
  { date: "2026-03-03", solv: 24, search_term: "coffee shop near me" },
  { date: "2026-03-10", solv: 24, search_term: "coffee shop near me" },
  { date: "2026-03-17", solv: 20, search_term: "coffee shop near me" },
  { date: "2026-03-24", solv: 24, search_term: "coffee shop near me" },
  { date: "2026-03-31", solv: 28, search_term: "coffee shop near me" },
  { date: "2026-04-07", solv: 24, search_term: "coffee shop near me" },
  { date: "2026-04-14", solv: 28, search_term: "coffee shop near me" },
  { date: "2026-04-21", solv: 32, search_term: "coffee shop near me" },
  { date: "2026-04-28", solv: 28, search_term: "coffee shop near me" },
  { date: "2026-05-05", solv: 32, search_term: "coffee shop near me" },
  { date: "2026-05-12", solv: 36, search_term: "coffee shop near me" },
  { date: "2026-05-19", solv: 32, search_term: "coffee shop near me" },
  { date: "2026-05-26", solv: 36, search_term: "coffee shop near me" },
  { date: "2026-06-02", solv: 40, search_term: "coffee shop near me" },
  { date: "2026-06-09", solv: 16, search_term: "coffee shop near me" },
  { date: "2026-06-16", solv: 16, search_term: "coffee shop near me" },
];

export const sampleRankTrend: RankTrendData = {
  location_id: "loc-1",
  location_name: "Downtown Branch",
  latest_scan: sampleScan,
  solv_history,
};
