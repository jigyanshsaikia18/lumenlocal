"use client";

import type { ReactNode } from "react";

import { useFeatureFlag } from "./FeatureFlagProvider";

interface FeatureGateProps {
  /** Stable feature key, e.g. "dashboard_health". */
  feature: string;
  children: ReactNode;
  /** Rendered when the feature is disabled. Defaults to nothing (fully hidden). */
  fallback?: ReactNode;
}

/**
 * Renders `children` only when `feature` is enabled for the current scope
 * (PRD §7 D-6: disabled dashboard sections are hidden, not merely greyed out).
 * When off it renders `fallback` (nothing by default) — no DOM, no API calls,
 * no broken layout.
 */
export function FeatureGate({ feature, children, fallback = null }: FeatureGateProps) {
  const enabled = useFeatureFlag(feature);
  return <>{enabled ? children : fallback}</>;
}
