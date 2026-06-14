import { FeatureGate } from "@/components/feature-flags/FeatureGate";
import { Card } from "@/components/ui/Card";
import { SEVERITY_RANK } from "@/lib/dashboard/metrics";
import type { GapSeverity, HealthScore } from "@/lib/dashboard/types";

import { ScoreRing } from "./ScoreRing";

/** Stable feature key gating this widget (PRD §7 D-6). */
export const HEALTH_SCORE_FEATURE = "dashboard_health";

const SEVERITY_DOT: Record<GapSeverity, string> = {
  high: "bg-negative",
  medium: "bg-amber-500",
  low: "bg-muted",
};

interface HealthScoreWidgetProps {
  data: HealthScore;
  /** Override the gating feature key (defaults to "dashboard_health"). */
  feature?: string;
}

/**
 * Profile Health Score (PRD §7 D-1): the optimization grade plus the specific
 * gaps driving it. Hidden entirely when its feature flag is off for the client.
 */
export function HealthScoreWidget({
  data,
  feature = HEALTH_SCORE_FEATURE,
}: HealthScoreWidgetProps) {
  const gaps = [...data.gaps].sort(
    (a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity] || b.impact - a.impact,
  );

  return (
    <FeatureGate feature={feature}>
      <Card className="p-6">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
          <ScoreRing value={data.score} grade={data.grade} />
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-semibold tracking-tight text-foreground">
              Profile Health
            </h2>
            <p className="mt-0.5 text-sm text-muted">
              {data.completeness}% complete · real-time optimization grade
            </p>
            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-hairline">
              <div
                className="h-full rounded-full bg-gradient-to-r from-brand to-accent"
                style={{ width: `${Math.max(0, Math.min(100, data.completeness))}%` }}
              />
            </div>
          </div>
        </div>

        <div className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
            Top gaps to close
          </h3>
          <ul className="mt-3 space-y-2">
            {gaps.length === 0 ? (
              <li className="text-sm text-muted">No gaps — this profile is fully optimized.</li>
            ) : (
              gaps.map((gap) => (
                <li
                  key={gap.id}
                  className="flex items-center justify-between gap-3 rounded-xl border border-hairline bg-canvas/40 px-3 py-2"
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <span
                      className={`h-2 w-2 shrink-0 rounded-full ${SEVERITY_DOT[gap.severity]}`}
                      aria-hidden
                    />
                    <span className="truncate text-sm text-foreground">{gap.label}</span>
                  </span>
                  <span className="shrink-0 text-xs font-semibold tabular-nums text-brand">
                    +{gap.impact} pts
                  </span>
                </li>
              ))
            )}
          </ul>
        </div>
      </Card>
    </FeatureGate>
  );
}
