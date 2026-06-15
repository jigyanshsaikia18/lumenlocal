/**
 * API client for the entitlement toggle engine (API spec §4).
 * All paths are relative to the Next.js rewrite proxy at /api/v1.
 */

const BASE = "/api/v1";

export interface ResolvedFeature {
  key: string;
  enabled: boolean;
  source: string;
}

export interface ClientPreviewResponse {
  client_id: string;
  role: string;
  features: ResolvedFeature[];
}

export interface ToggleResponse {
  feature_key: string;
  level: string;
  scope_id: string;
  previous_state: boolean | null;
  state: boolean;
}

export async function fetchClientPreview(
  clientId: string,
  role = "client_owner",
): Promise<ClientPreviewResponse> {
  const res = await fetch(`${BASE}/clients/${clientId}/preview?role=${encodeURIComponent(role)}`);
  if (!res.ok) throw new Error(`Preview failed: ${res.status}`);
  return res.json();
}

export async function toggleClientFeature(
  clientId: string,
  featureKey: string,
  state: boolean,
): Promise<ToggleResponse> {
  const res = await fetch(`${BASE}/clients/${clientId}/features/${featureKey}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state }),
  });
  if (!res.ok) throw new Error(`Toggle failed: ${res.status}`);
  return res.json();
}

export async function toggleLocationFeature(
  locationId: string,
  featureKey: string,
  state: boolean,
): Promise<ToggleResponse> {
  const res = await fetch(`${BASE}/locations/${locationId}/features/${featureKey}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state }),
  });
  if (!res.ok) throw new Error(`Toggle failed: ${res.status}`);
  return res.json();
}
