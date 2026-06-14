/**
 * Dashboard data contracts (PRD §7 Module 1). Shapes mirror the responses of
 * `GET /locations/{id}/health-score` (D-1) and
 * `GET /locations/{id}/performance` (D-2).
 */

export type GapSeverity = "high" | "medium" | "low";

/** A specific gap driving the health score down (D-1: "the gaps driving the score"). */
export interface HealthGap {
  id: string;
  label: string;
  /** Points recoverable by fixing this gap. */
  impact: number;
  severity: GapSeverity;
}

export interface HealthScore {
  /** Overall optimization grade, 0–100. */
  score: number;
  /** Letter grade derived from the score (A–F). */
  grade: string;
  /** Profile completeness, 0–100. */
  completeness: number;
  gaps: HealthGap[];
}

export interface PerformancePeriod {
  /** ISO-8601 date (inclusive). */
  from: string;
  /** ISO-8601 date (inclusive). */
  to: string;
}

/** One GBP Performance API metric with its prior-period value for comparison (D-2). */
export interface PerformanceMetric {
  key: string;
  label: string;
  value: number;
  /** Same metric over the immediately preceding period of equal length. */
  previousValue: number;
}

export interface PerformanceSummary {
  period: PerformancePeriod;
  comparisonPeriod: PerformancePeriod;
  metrics: PerformanceMetric[];
}
