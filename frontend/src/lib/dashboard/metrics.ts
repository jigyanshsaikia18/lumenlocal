import type { GapSeverity } from "./types";

export type TrendDirection = "up" | "down" | "flat";

export interface Delta {
  absolute: number;
  /** Percent change vs the previous period; null when there is no prior baseline. */
  percent: number | null;
  direction: TrendDirection;
}

/** Period-over-period change for a metric (D-2: "with period comparisons"). */
export function computeDelta(value: number, previous: number): Delta {
  const absolute = value - previous;
  const direction: TrendDirection = absolute > 0 ? "up" : absolute < 0 ? "down" : "flat";
  const percent = previous === 0 ? null : (absolute / previous) * 100;
  return { absolute, percent, direction };
}

/** Compact display of large counts (e.g. 12_400 → "12.4k"). */
export function formatCount(value: number): string {
  if (Math.abs(value) >= 1000) {
    return `${(value / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  }
  return value.toLocaleString("en-US");
}

export function formatPercent(value: number | null): string {
  if (value === null) return "—";
  const rounded = Math.round(Math.abs(value) * 10) / 10;
  return `${value > 0 ? "+" : value < 0 ? "-" : ""}${rounded}%`;
}

/** Map a 0–100 score to a letter grade for the health ring. */
export function scoreToGrade(score: number): string {
  if (score >= 90) return "A";
  if (score >= 80) return "B";
  if (score >= 70) return "C";
  if (score >= 60) return "D";
  return "F";
}

export const SEVERITY_RANK: Record<GapSeverity, number> = {
  high: 0,
  medium: 1,
  low: 2,
};
