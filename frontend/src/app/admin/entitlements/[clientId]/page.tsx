"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { FeatureToggleRow } from "@/components/admin/FeatureToggleRow";
import {
  fetchClientPreview,
  toggleClientFeature,
  toggleLocationFeature,
  type ResolvedFeature,
} from "@/lib/api/entitlements";

const PREVIEW_ROLES = ["client_owner", "account_manager", "analyst"] as const;

interface LocationScope {
  id: string;
  name: string;
  features: ResolvedFeature[];
}

export default function EntitlementsAdminPage() {
  const params = useParams();
  const clientId = Array.isArray(params.clientId) ? params.clientId[0] : (params.clientId ?? "");

  const [role, setRole] = useState("client_owner");
  const [features, setFeatures] = useState<ResolvedFeature[]>([]);
  const [locations, setLocations] = useState<LocationScope[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!clientId) return;
    setLoading(true);
    setError(null);
    try {
      const preview = await fetchClientPreview(clientId, role);
      setFeatures(preview.features);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load entitlements");
    } finally {
      setLoading(false);
    }
  }, [clientId, role]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleClientToggle(key: string, state: boolean) {
    await toggleClientFeature(clientId, key, state);
    await load();
  }

  async function handleLocationToggle(locationId: string, key: string, state: boolean) {
    await toggleLocationFeature(locationId, key, state);
    // Refresh — a location toggle may change the client-level resolved view.
    await load();
  }

  const featureName = (key: string) =>
    key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <header className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-muted">
          Super-Admin
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
          Entitlement Admin
        </h1>
        <p className="mt-1 font-mono text-sm text-muted">Client: {clientId}</p>
      </header>

      {/* Role preview selector */}
      <div className="mb-6 flex items-center gap-3">
        <label
          htmlFor="role-select"
          className="text-sm font-medium text-foreground"
        >
          Preview as:
        </label>
        <select
          id="role-select"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="rounded-lg border border-hairline bg-surface px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-brand"
        >
          {PREVIEW_ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <span className="text-xs text-muted">
          (shows resolved state — source label indicates where the override originates)
        </span>
      </div>

      {/* Client-level toggles */}
      <section
        aria-label="Client-level features"
        className="mb-8 overflow-hidden rounded-xl border border-hairline bg-surface shadow-card"
      >
        <div className="border-b border-hairline px-4 py-3">
          <h2 className="text-sm font-semibold text-foreground">Client-level features</h2>
          <p className="mt-0.5 text-xs text-muted">
            Overrides apply to every location under this client.
          </p>
        </div>

        {loading && (
          <p className="px-4 py-6 text-sm text-muted">Loading…</p>
        )}
        {error && (
          <p className="px-4 py-6 text-sm text-negative" role="alert">
            {error}
          </p>
        )}
        {!loading && !error && features.length === 0 && (
          <p className="px-4 py-6 text-sm text-muted">No features registered.</p>
        )}
        {!loading &&
          !error &&
          features.map((f) => (
            <FeatureToggleRow
              key={f.key}
              featureKey={f.key}
              featureName={featureName(f.key)}
              enabled={f.enabled}
              source={f.source}
              onToggle={handleClientToggle}
            />
          ))}
      </section>

      {/* Location-level toggles */}
      {locations.length > 0 && (
        <section aria-label="Location-level features">
          <h2 className="mb-4 text-base font-semibold text-foreground">
            Location-level overrides
          </h2>
          {locations.map((loc) => (
            <div
              key={loc.id}
              className="mb-6 overflow-hidden rounded-xl border border-hairline bg-surface shadow-card"
            >
              <div className="border-b border-hairline px-4 py-3">
                <h3 className="text-sm font-semibold text-foreground">{loc.name}</h3>
                <p className="mt-0.5 font-mono text-xs text-muted">{loc.id}</p>
              </div>
              {loc.features.map((f) => (
                <FeatureToggleRow
                  key={f.key}
                  featureKey={f.key}
                  featureName={featureName(f.key)}
                  enabled={f.enabled}
                  source={f.source}
                  onToggle={(key, state) => handleLocationToggle(loc.id, key, state)}
                />
              ))}
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
