import { FeatureGate } from "@/components/feature-flags/FeatureGate";
import { Card, CardHeader } from "@/components/ui/Card";
import type { PerformanceSummary } from "@/lib/dashboard/types";

import { MetricCard } from "./MetricCard";

/** Stable feature key gating this widget (PRD §7 D-6). */
export const PERFORMANCE_FEATURE = "dashboard_performance";

interface PerformanceWidgetProps {
  data: PerformanceSummary;
  /** Override the gating feature key (defaults to "dashboard_performance"). */
  feature?: string;
}

function formatRange({ from, to }: { from: string; to: string }): string {
  const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
  const f = new Date(from).toLocaleDateString("en-US", opts);
  const t = new Date(to).toLocaleDateString("en-US", opts);
  return `${f} – ${t}`;
}

/**
 * GBP Performance metrics (PRD §7 D-2): calls, website clicks, direction
 * requests, branded/discovery searches and views, each with a period-over-period
 * comparison. Hidden entirely when its feature flag is off for the client.
 */
export function PerformanceWidget({
  data,
  feature = PERFORMANCE_FEATURE,
}: PerformanceWidgetProps) {
  return (
    <FeatureGate feature={feature}>
      <Card>
        <CardHeader
          title="Performance"
          subtitle={`${formatRange(data.period)} · vs ${formatRange(data.comparisonPeriod)}`}
        />
        <div className="grid grid-cols-1 gap-3 p-6 pt-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.metrics.map((metric) => (
            <MetricCard key={metric.key} metric={metric} />
          ))}
        </div>
      </Card>
    </FeatureGate>
  );
}
