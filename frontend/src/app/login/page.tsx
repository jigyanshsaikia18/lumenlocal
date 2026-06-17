"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { login } from "@/lib/api/auth";
import { storeToken } from "@/lib/auth/token";

/**
 * Minimal email + password login (P1B-1 frontend). On success the access token
 * is stored client-side and the user lands on /dashboard. MFA-enabled accounts
 * need the /auth/mfa/verify flow, which isn't wired into this form yet.
 */
export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await login(email, password);
      if (res.mfa_required) {
        setError("This account requires multi-factor authentication, which isn't supported here yet.");
        return;
      }
      if (!res.access_token) {
        setError("Login succeeded but no access token was returned.");
        return;
      }
      storeToken(res.access_token);
      router.replace("/dashboard");
    } catch (err) {
      setError(
        err instanceof Error && err.message === "invalid_credentials"
          ? "Email or password is incorrect."
          : "Something went wrong. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-5 rounded-lg border border-gray-200 p-8 shadow-sm"
      >
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Sign in to LumenLocal</h1>
          <p className="mt-1 text-sm text-gray-500">Use your agency or client account.</p>
        </div>

        <div className="space-y-1">
          <label htmlFor="email" className="block text-sm font-medium">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
          />
        </div>

        <div className="space-y-1">
          <label htmlFor="password" className="block text-sm font-medium">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
          />
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
