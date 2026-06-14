"use client";

import { createContext, useContext, type ReactNode } from "react";

/**
 * Resolved entitlement set for the current scope — the on/off map returned by
 * `GET /entitlements/resolve` (the backend's location > client > plan > default
 * resolver). Keys are stable feature keys (e.g. "dashboard_health").
 */
export type FeatureFlags = Record<string, boolean>;

const FeatureFlagContext = createContext<FeatureFlags>({});

interface FeatureFlagProviderProps {
  flags: FeatureFlags;
  children: ReactNode;
}

export function FeatureFlagProvider({ flags, children }: FeatureFlagProviderProps) {
  return (
    <FeatureFlagContext.Provider value={flags}>{children}</FeatureFlagContext.Provider>
  );
}

/**
 * Whether a feature is enabled for the current scope. Fail-closed: an unknown or
 * absent key is treated as OFF, matching the backend's fail-closed resolution so
 * a missing entitlement never accidentally exposes a feature.
 */
export function useFeatureFlag(key: string): boolean {
  const flags = useContext(FeatureFlagContext);
  return flags[key] === true;
}
