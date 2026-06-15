/**
 * P1C-3 acceptance: toggling in the UI calls the right endpoint.
 *
 * Tests:
 * - FeatureToggleRow renders on/off state correctly.
 * - Clicking the toggle calls onToggle with the inverted state.
 * - toggleClientFeature PUTs to /api/v1/clients/:id/features/:key.
 * - toggleLocationFeature PUTs to /api/v1/locations/:id/features/:key.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FeatureToggleRow } from "@/components/admin/FeatureToggleRow";
import { toggleClientFeature, toggleLocationFeature } from "@/lib/api/entitlements";

// ---------------------------------------------------------------------------
// FeatureToggleRow — unit tests (no fetch, pure rendering + callback)
// ---------------------------------------------------------------------------

describe("FeatureToggleRow", () => {
  it("renders the feature name and key", () => {
    render(
      <FeatureToggleRow
        featureKey="geogrid"
        featureName="Geo Grid"
        enabled={true}
        source="default"
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getByText("Geo Grid")).toBeInTheDocument();
    expect(screen.getByText("geogrid")).toBeInTheDocument();
  });

  it("shows aria-checked=true when enabled", () => {
    render(
      <FeatureToggleRow
        featureKey="geogrid"
        featureName="Geo Grid"
        enabled={true}
        source="client"
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getByRole("switch", { name: "Geo Grid" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("shows aria-checked=false when disabled", () => {
    render(
      <FeatureToggleRow
        featureKey="geogrid"
        featureName="Geo Grid"
        enabled={false}
        source="default"
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getByRole("switch", { name: "Geo Grid" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("calls onToggle with key and false when currently enabled", () => {
    const onToggle = vi.fn();
    render(
      <FeatureToggleRow
        featureKey="geogrid"
        featureName="Geo Grid"
        enabled={true}
        source="default"
        onToggle={onToggle}
      />,
    );
    fireEvent.click(screen.getByRole("switch", { name: "Geo Grid" }));
    expect(onToggle).toHaveBeenCalledWith("geogrid", false);
  });

  it("calls onToggle with key and true when currently disabled", () => {
    const onToggle = vi.fn();
    render(
      <FeatureToggleRow
        featureKey="review_inbox"
        featureName="Review Inbox"
        enabled={false}
        source="default"
        onToggle={onToggle}
      />,
    );
    fireEvent.click(screen.getByRole("switch", { name: "Review Inbox" }));
    expect(onToggle).toHaveBeenCalledWith("review_inbox", true);
  });

  it("shows the Client source badge when source is client", () => {
    render(
      <FeatureToggleRow
        featureKey="geogrid"
        featureName="Geo Grid"
        enabled={false}
        source="client"
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getByText("Client")).toBeInTheDocument();
  });

  it("shows the Default source badge when source is default", () => {
    render(
      <FeatureToggleRow
        featureKey="geogrid"
        featureName="Geo Grid"
        enabled={true}
        source="default"
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getByText("Default")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// API call wiring — integration tests (mock fetch)
// ---------------------------------------------------------------------------

const mockOkResponse = () =>
  Promise.resolve({
    ok: true,
    json: () =>
      Promise.resolve({
        feature_key: "geogrid",
        level: "client",
        scope_id: "client-abc",
        previous_state: null,
        state: false,
      }),
  });

describe("toggleClientFeature", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(mockOkResponse));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("PUTs to /api/v1/clients/:id/features/:key", async () => {
    await toggleClientFeature("client-abc", "geogrid", false);
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/clients/client-abc/features/geogrid",
      expect.objectContaining({ method: "PUT" }),
    );
  });

  it("sends state:false in the body when disabling", async () => {
    await toggleClientFeature("client-abc", "geogrid", false);
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ state: false });
  });

  it("sends state:true in the body when enabling", async () => {
    await toggleClientFeature("client-abc", "review_inbox", true);
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ state: true });
  });

  it("sets Content-Type: application/json", async () => {
    await toggleClientFeature("client-abc", "geogrid", false);
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
  });
});

describe("toggleLocationFeature", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(mockOkResponse));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("PUTs to /api/v1/locations/:id/features/:key", async () => {
    await toggleLocationFeature("loc-xyz", "geogrid", false);
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/locations/loc-xyz/features/geogrid",
      expect.objectContaining({ method: "PUT" }),
    );
  });

  it("sends the correct state in the body", async () => {
    await toggleLocationFeature("loc-xyz", "geogrid", true);
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ state: true });
  });
});
