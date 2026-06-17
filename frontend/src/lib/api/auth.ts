/**
 * API client for auth endpoints (API spec §2, P1B-1).
 * Paths are relative to the Next.js rewrite proxy at /api/v1.
 */

const BASE = "/api/v1";

export interface LoginResponse {
  mfa_required: boolean;
  mfa_token: string | null;
  access_token: string | null;
  refresh_token: string | null;
  token_type: string;
}

/**
 * Exchange email + password for a token pair (or an MFA challenge).
 * Throws Error("invalid_credentials") on 401 so the form can show a friendly message.
 */
export async function login(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (res.status === 401) throw new Error("invalid_credentials");
  if (!res.ok) throw new Error(`Login failed: ${res.status}`);
  return res.json();
}
