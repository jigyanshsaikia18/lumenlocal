/**
 * P1B-1 acceptance: the login form talks to the right endpoint and surfaces
 * credential errors.
 *
 * Tests:
 * - login POSTs email + password to /api/v1/auth/login as JSON.
 * - a 401 response throws Error("invalid_credentials").
 * - a successful response returns the parsed token payload.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { login } from "@/lib/api/auth";

const okPayload = {
  mfa_required: false,
  mfa_token: null,
  access_token: "jwt-abc",
  refresh_token: "jwt-refresh",
  token_type: "bearer",
};

describe("login", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs credentials to /api/v1/auth/login", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve(okPayload) }),
    );
    await login("user@example.com", "hunter2");
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/auth/login",
      expect.objectContaining({ method: "POST" }),
    );
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ email: "user@example.com", password: "hunter2" });
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
  });

  it("returns the parsed token payload on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve(okPayload) }),
    );
    await expect(login("user@example.com", "hunter2")).resolves.toEqual(okPayload);
  });

  it("throws invalid_credentials on a 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 401, json: () => Promise.resolve({}) }),
    );
    await expect(login("user@example.com", "wrong")).rejects.toThrow("invalid_credentials");
  });
});
