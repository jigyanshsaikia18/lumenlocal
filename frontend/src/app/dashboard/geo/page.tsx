import { FeatureFlagProvider } from "@/components/feature-flags/FeatureFlagProvider";
import { GeoDashboardWidget, GEO_DASHBOARD_FEATURE } from "@/components/geo/GeoDashboardWidget";
import { sampleGeoDashboard } from "@/lib/geo/sample";

/**
 * P2C-5 — GEO dashboard demo page.
 * In production this page fetches from GET /locations/{id}/geo-ai-scans.
 */
export default function GeoDashboardPage() {
  return (
    <FeatureFlagProvider flags={{ [GEO_DASHBOARD_FEATURE]: true }}>
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="mb-6 text-2xl font-bold tracking-tight text-foreground">
          GEO Dashboard
        </h1>
        <GeoDashboardWidget data={sampleGeoDashboard} />
      </main>
    </FeatureFlagProvider>
  );
}
