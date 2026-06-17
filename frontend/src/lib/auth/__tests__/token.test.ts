/**
 * P1B-1: token storage helpers back the auth guard's isAuthenticated() check.
 */
import { afterEach, describe, expect, it } from "vitest";

import { clearToken, getToken, isAuthenticated, storeToken } from "@/lib/auth/token";

describe("token storage", () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it("returns null and unauthenticated when no token is stored", () => {
    expect(getToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it("round-trips a stored token", () => {
    storeToken("jwt-abc");
    expect(getToken()).toBe("jwt-abc");
    expect(isAuthenticated()).toBe(true);
  });

  it("clears a stored token", () => {
    storeToken("jwt-abc");
    clearToken();
    expect(getToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });
});
