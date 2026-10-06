import { redirect } from "next/navigation";

import { apiFetch, ApiNotAuthenticated } from "@/lib/api";
import { getProfile, type Profile } from "@/lib/profile";
import type { SessionProfile } from "@/lib/types";

/**
 * Session guard for the authenticated pages.
 *
 * The distinction this file exists to make: **no session** and **the API
 * failed** are different things.
 *
 * Redirecting to `/login` on any error turns a rate limit, a timeout or a
 * database blip into a redirect loop — the login page sees a cookie still in
 * the jar, sends the user back, the dashboard fails again, and around it goes.
 * Only a genuinely absent session redirects; everything else is surfaced.
 */

export type SessionResult =
  | { kind: "ok"; profile: Profile }
  | { kind: "unauthenticated" }
  | { kind: "unavailable"; message: string };

export async function requireSession(): Promise<SessionResult> {
  let profile: Profile | null;
  try {
    profile = await getProfile();
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) return { kind: "unauthenticated" };
    return {
      kind: "unavailable",
      message:
        error instanceof Error
          ? error.message
          : "No fue posible contactar con el servicio.",
    };
  }

  if (profile === null) return { kind: "unauthenticated" };
  return { kind: "ok", profile };
}

/**
 * Load a resource for a signed-in caller.
 *
 * Redirects only when the session is genuinely gone. A failure that is not an
 * authentication problem returns null so the caller can render an empty state:
 * absence of data is not a failure, and neither is a backend that is briefly
 * unavailable.
 */
export async function loadForSession<T>(
  path: string,
  options: { query?: Record<string, string | number | boolean> } = {},
): Promise<{ value: T | null; failed: boolean }> {
  try {
    return { value: await apiFetch<T>(path, { query: options.query }), failed: false };
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) redirect("/login");
    return { value: null, failed: true };
  }
}

export type { SessionProfile };
