import { computeDelta, formatCount, formatPercent } from "@/lib/dashboard/metrics";
import type { PerformanceMetric } from "@/lib/dashboard/types";

const DIRECTION_STYLES = {
  up: "bg-positive/10 text-positive",
  down: "bg-negative/10 text-negative",
  flat: "bg-muted/10 text-muted",
} as const;

const ARROW = { up: "↑", down: "↓", flat: "→" } as const;

/** A single GBP performance metric tile with its period-over-period delta badge. */
export function MetricCard({ metric }: { metric: PerformanceMetric }) {
  const delta = computeDelta(metric.value, metric.previousValue);

  return (
    <div className="rounded-xl border border-hairline bg-canvas/40 p-4">
      <p className="text-sm font-medium text-muted">{metric.label}</p>
      <div className="mt-2 flex items-end justify-between gap-2">
        <span className="text-2xl font-semibold tabular-nums text-foreground">
          {formatCount(metric.value)}
        </span>
        <span
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ${DIRECTION_STYLES[delta.direction]}`}
          aria-label={`${delta.direction} ${formatPercent(delta.percent)} versus previous period`}
        >
          <span aria-hidden>{ARROW[delta.direction]}</span>
          {formatPercent(delta.percent)}
        </span>
      </div>
      <p className="mt-1 text-xs text-muted">
        vs {formatCount(metric.previousValue)} prior period
      </p>
    </div>
  );
}
