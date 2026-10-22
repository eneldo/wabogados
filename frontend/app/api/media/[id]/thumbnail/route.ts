/**
 * Serves the JPEG poster of a media asset, credentials attached server side.
 *
 * Why it exists: the listing is a server component, so it cannot carry the
 * session cookie to the API as the browser would; this route handler attaches
 * the token from the httpOnly cookie, exactly like the streaming route. It must
 * not be the shared `/api/proxy/[...path]` either — not because of the body
 * (a JPEG is small), but because a 404 of a missing poster must reach the cell
 * *as a 404*: an empty 200 or a proxied HTML error page would surface as a
 * broken image rather than the clean fallback the cell wants.
 */

import { NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/api";
import { readAccessToken, refreshSession } from "@/lib/session";

type Context = { params: Promise<{ id: string }> };

/** Headers copied from the API to the browser. */
const PASSTHROUGH = [
  "content-type",
  "content-length",
  "content-disposition",
  "x-content-sha256",
] as const;

async function serve(context: Context, bearer: string): Promise<Response> {
  const { id } = await context.params;

  const upstream = await fetch(
    `${apiBaseUrl()}/api/v1/media/${encodeURIComponent(id)}/thumbnail`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${bearer}` },
      cache: "no-store",
    },
  );

  const out: Record<string, string> = { "Cache-Control": "no-store" };
  for (const name of PASSTHROUGH) {
    const value = upstream.headers.get(name);
    if (value) out[name] = value;
  }

  // The status is copied, not invented: the missing poster is a real 404 here.
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export async function GET(_request: Request, context: Context): Promise<Response> {
  const token = await readAccessToken();
  if (!token) {
    return NextResponse.json(
      { error: { message: "Sesión no iniciada." } },
      { status: 401 },
    );
  }

  const response = await serve(context, token);

  // A token can lapse between renders; one renewal attempt, same as the stream.
  if (response.status === 401) {
    const renewed = await refreshSession();
    if (renewed) return serve(context, renewed);
  }

  return response;
}
