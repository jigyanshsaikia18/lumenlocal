import { CommandCenterWidget } from "@/components/dashboard/CommandCenterWidget";
import {
  FeatureFlagProvider,
  type FeatureFlags,
} from "@/components/feature-flags/FeatureFlagProvider";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { sampleCommandCenter } from "@/lib/dashboard/sample";

/**
 * Multi-location command center (PRD §7 D-3, P1E-2). In production the flags
 * come from `GET /entitlements/resolve` and the data from
 * `GET /clients/{id}/command-center`; here they are inlined so the page is
 * viewable end-to-end without a running API.
 */
const resolvedFlags: FeatureFlags = {
  dashboard_multi_location: true,
};

export default function CommandCenterPage() {
  return (
    <ThemeProvider>
      <FeatureFlagProvider flags={resolvedFlags}>
        <main className="mx-auto min-h-screen w-full max-w-6xl px-6 py-10">
          <header className="mb-8">
            <p className="text-sm font-medium text-brand">
              Riverside Dental · 5 locations
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
              Command Center
            </h1>
          </header>
          <CommandCenterWidget data={sampleCommandCenter} />
        </main>
      </FeatureFlagProvider>
    </ThemeProvider>
  );
}
