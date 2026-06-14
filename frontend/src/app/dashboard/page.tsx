import { HealthScoreWidget } from "@/components/dashboard/HealthScoreWidget";
import { PerformanceWidget } from "@/components/dashboard/PerformanceWidget";
import {
  FeatureFlagProvider,
  type FeatureFlags,
} from "@/components/feature-flags/FeatureFlagProvider";
import { ThemeProvider, type BrandTheme } from "@/components/theme/ThemeProvider";
import { sampleHealthScore, samplePerformance } from "@/lib/dashboard/sample";

/**
 * Demo dashboard (PRD §7 Module 1). In production the flags come from
 * `GET /entitlements/resolve` and the theme from the tenant's white-label config;
 * here they are inlined so the premium, themeable result is viewable end-to-end.
 */

// Example agency white-label override — swap to see the whole dashboard re-skin.
const agencyTheme: BrandTheme | undefined = undefined;

const resolvedFlags: FeatureFlags = {
  dashboard_health: true,
  dashboard_performance: true,
};

export default function DashboardPage() {
  return (
    <ThemeProvider theme={agencyTheme}>
      <FeatureFlagProvider flags={resolvedFlags}>
        <main className="mx-auto min-h-screen w-full max-w-6xl px-6 py-10">
          <header className="mb-8">
            <p className="text-sm font-medium text-brand">Riverside Dental · Downtown</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
              Location dashboard
            </h1>
          </header>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
            <div className="lg:col-span-2">
              <HealthScoreWidget data={sampleHealthScore} />
            </div>
            <div className="lg:col-span-3">
              <PerformanceWidget data={samplePerformance} />
            </div>
          </div>
        </main>
      </FeatureFlagProvider>
    </ThemeProvider>
  );
}
