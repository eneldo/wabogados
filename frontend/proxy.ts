/**
 * Session refresh, before rendering.
 *
 * The access token lives thirty minutes and the refresh token seven days. This
 * file is where that gap is closed, and the location is not incidental:
 *
 * - A Server Component **cannot** write cookies. Setting one during a render
 *   does not update the cookie jar for the rest of that same render, so a
 *   refresh attempted there retries with the token it just replaced. Worse, the
 *   backend rotates the refresh token, so the second attempt presents a token
 *   that no longer exists and destroys the session that had just been renewed.
 * - Middleware runs before rendering and its cookie writes reach the response,
 *   so by the time a page reads the jar it holds a token that works.
 *
 * The expiry is read from the token without verifying it. Verification is the
 * API's job; here it only decides whether to bother asking for a new one, and a
 * forged `exp` gets us a 401 from the API and nothing else.
 */

import { NextResponse, type NextRequest } from "next/server";

const ACCESS_COOKIE = "wb_access";
const REFRESH_COOKIE = "wb_refresh";

/** Renew this long before expiry, so a token cannot lapse mid-render. */
const RENEW_WINDOW_SECONDS = 60;

const API_URL = (process.env.API_INTERNAL_URL ?? "http://localhost:8000").replace(
  /\/+$/,
  "");

/** Decoded `exp` of a JWT, or null when it cannot be read. */
function expiresAt(token: string | undefined): number | null {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const payload = JSON.parse(
      Buffer.from(parts[1], "base64url").toString("utf8"),
    ) as { exp?: unknown };
    return typeof payload.exp === "number" ? payload.exp : null;
  } catch {
    return null;
  }
}

function needsRenewal(token: string | undefined): boolean {
  const exp = expiresAt(token);
  // No readable expiry: ask anyway. The API is the only authority that matters,
  // and a needless refresh costs one request.
  if (exp === null) return true;
  return exp - RENEW_WINDOW_SECONDS <= Math.floor(Date.now() / 1000);
}

export async function proxy(request: NextRequest): Promise<NextResponse> {
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;

  if (!refresh || !needsRenewal(access)) {
    return NextResponse.next();
  }

  let renewed: { access_token?: string; refresh_token?: string };
  try {
    const response = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
      cache: "no-store",
    });
    if (!response.ok) {
      // The refresh token is spent or revoked. Clearing the jar stops the rest
      // of the request from presenting a token that cannot work, and the login
      // page takes over on the next navigation.
      if (response.status === 401) {
        const cleared = NextResponse.next();
        cleared.cookies.delete(ACCESS_COOKIE);
        cleared.cookies.delete(REFRESH_COOKIE);
        return cleared;
      }
      return NextResponse.next();
    }
    renewed = (await response.json()) as {
      access_token?: string;
      refresh_token?: string;
    };
  } catch {
    // The API is unreachable. Keep the session: a network problem is not a
    // reason to sign a lawyer out of their case file.
    return NextResponse.next();
  }

  if (!renewed.access_token) return NextResponse.next();

  const response = NextResponse.next();
  const secure = process.env.NODE_ENV === "production";
  response.cookies.set(ACCESS_COOKIE, renewed.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: 60 * 60 * 12,
  });
  response.cookies.set(REFRESH_COOKIE, renewed.refresh_token ?? refresh, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return response;
}

export const config = {
  /*
   * The static assets and the session endpoint are excluded: the first has no
   * cookie worth renewing and the second is what creates one.
   */
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/session).*)"],
};
