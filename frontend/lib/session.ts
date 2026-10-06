/**
 * Session cookies.
 *
 * The access and refresh tokens live in `httpOnly` cookies set by the server.
 * They are deliberately never handed to client JavaScript: a token reachable
 * from the page is a token an XSS can take, and this application holds a
 * lawyer's whole case book. Client components talk to `/api/proxy/*` instead,
 * which attaches the credential server side.
 */

import { cookies } from "next/headers";

import { apiBaseUrl } from "./api";

export const ACCESS_COOKIE = "wb_access";
export const REFRESH_COOKIE = "wb_refresh";

/** Twelve hours. The access token itself expires in thirty minutes. */
const ACCESS_TTL_SECONDS = 60 * 60 * 12;

/** Seven days, matching the backend's refresh token lifetime. */
const REFRESH_TTL_SECONDS = 60 * 60 * 24 * 7;

export type SessionTokens = {
  accessToken: string;
  refreshToken: string;
  /** The access token, as returned by the login endpoint, if it carried one. */
  refreshExpiresIn?: number;
};

export type SessionProfile = {
  id: string;
  email: string;
  fullName: string;
  roles: string[];
  permissions: string[];
};

const baseCookie = {
  httpOnly: true as const,
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
  path: "/",
};

export async function readAccessToken(): Promise<string | undefined> {
  const jar = await cookies();
  return jar.get(ACCESS_COOKIE)?.value;
}

export async function readRefreshToken(): Promise<string | undefined> {
  const jar = await cookies();
  return jar.get(REFRESH_COOKIE)?.value;
}

export async function writeSession(tokens: SessionTokens): Promise<void> {
  const jar = await cookies();
  jar.set(ACCESS_COOKIE, tokens.accessToken, {
    ...baseCookie,
    maxAge: ACCESS_TTL_SECONDS,
  });
  jar.set(REFRESH_COOKIE, tokens.refreshToken, {
    ...baseCookie,
    maxAge: REFRESH_TTL_SECONDS,
  });
}

export async function clearSession(): Promise<void> {
  const jar = await cookies();
  jar.delete(ACCESS_COOKIE);
  jar.delete(REFRESH_COOKIE);
}

/**
 * Revoke this session on the server, then let the caller drop the cookies.
 *
 * Dropping the cookies is not signing out. The refresh token lives in the
 * database for seven days, so a cookie jar copied before sign-out — or a token
 * that leaked some other way — keeps minting access tokens long after the
 * person believed they had left.
 *
 * Only the session that is signing out is revoked, not every session of the
 * account: closing a laptop must not end the work on the phone.
 *
 * **Never fails.** A sign-out that ends on an error page leaves the person
 * logged in, which is the opposite of what they asked for, so a network or
 * server failure is swallowed and the cookies are cleared anyway. The cost of
 * that choice is stated in `NEXT_STEPS.md`: an unreachable API leaves the
 * refresh token valid until it expires on its own.
 */
export async function revokeSession(): Promise<boolean> {
  const refreshToken = await readRefreshToken();
  const accessToken = await readAccessToken();
  if (!refreshToken || !accessToken) return false;

  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/auth/logout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Exchange the refresh token for a new access token.
 *
 * Returns the **new access token** rather than making the caller read it back
 * from the cookie jar. A route handler that set the cookie and then re-read it
 * would get the value it was trying to replace, and would retry with the
 * expired token it already knew was bad.
 *
 * Only for Route Handlers. A Server Component cannot set cookies at all; that
 * job belongs to `proxy.ts`.
 */
export async function refreshSession(): Promise<string | null> {
  const refreshToken = await readRefreshToken();
  if (!refreshToken) return null;

  let payload: { access_token?: string; refresh_token?: string };
  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
    if (!response.ok) {
      // Rejected or spent: the session really is over. A network failure is
      // not, and is handled by the catch below.
      if (response.status === 401) await clearSession();
      return null;
    }
    payload = (await response.json()) as {
      access_token?: string;
      refresh_token?: string;
    };
  } catch {
    return null;
  }

  if (!payload.access_token) return null;

  await writeSession({
    accessToken: payload.access_token,
    // The backend rotates the refresh token; keeping the current one when it
    // does not send a replacement avoids dropping a session over a field.
    refreshToken: payload.refresh_token ?? refreshToken,
  });
  return payload.access_token;
}
