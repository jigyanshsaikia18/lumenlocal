"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { isAuthenticated } from "@/lib/auth/token";

/**
 * Client-side route guard (P1B-1). Wrap protected route trees (dashboard, admin)
 * so unauthenticated visitors are redirected to /login. The token lives in
 * localStorage, which is only readable in the browser, so the check runs after
 * mount and renders nothing until it resolves to avoid a protected-content flash.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    if (isAuthenticated()) {
      setAllowed(true);
    } else {
      router.replace("/login");
    }
  }, [router]);

  if (!allowed) return null;
  return <>{children}</>;
}
