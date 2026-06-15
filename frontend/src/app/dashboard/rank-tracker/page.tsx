import { FeatureFlagProvider } from "@/components/feature-flags/FeatureFlagProvider";
import { RankTrackerWidget, RANK_TRACKER_FEATURE } from "@/components/ranking/RankTrackerWidget";
import { sampleRankTrend } from "@/lib/ranking/sample";

/**
 * P2B-3 — Rank Tracker demo page.
 * In production this page fetches from GET /locations/{id}/geogrid-scans.
 */
export default function RankTrackerPage() {
  return (
    <FeatureFlagProvider flags={{ [RANK_TRACKER_FEATURE]: true }}>
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="mb-6 text-2xl font-bold tracking-tight text-foreground">
          Rank Tracker
        </h1>
        <RankTrackerWidget data={sampleRankTrend} />
      </main>
    </FeatureFlagProvider>
  );
}
