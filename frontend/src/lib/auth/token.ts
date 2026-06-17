/**
 * Client-side JWT storage (P1B-1 frontend).
 *
 * The access token from POST /auth/login is kept in localStorage so it survives
 * reloads. SSR-safe: every accessor guards on `window` because these run during
 * Next.js server rendering too.
 */

const ACCESS_TOKEN_KEY = "lumenlocal.access_token";

export function storeToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}
