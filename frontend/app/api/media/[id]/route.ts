/**
 * Streams one media file to the browser, with the credential attached server side.
 *
 * **Why this is not the shared proxy.** `/api/proxy/[...path]` reads the upstream
 * body with `text()` and hands it back as a string, which is right for JSON and
 * wrong for a video: a `<video>` element asks for byte ranges, expects `206` with
 * a `Content-Range`, and cannot seek in a body that arrives whole and flattened.
 * Widening the general proxy to media would have meant teaching it to stream.
 *
 * **Why the token is not in the URL.** A media URL is the one address in this
 * application that a person pastes to somebody else, ends up in a `Referer` and
 * sits in browser history. The identifier is not a secret, the token is, so the
 * token stays in the httpOnly cookie and this route attaches it. The same reason
 * the downloads go through a route handler rather than a link with a query string.
 *
 * Only `GET` exists: the file is read, never written, from the browser's point of
 * view. Uploading is a Server Action.
 */

import { NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/api";
import { readAccessToken, refreshSession } from "@/lib/session";

type Context = { params: Promise<{ id: string }> };

/** Headers copied from the API to the browser. */
const PASSTHROUGH = [
  "content-type",
  "content-length",
  "content-range",
  "content-disposition",
  "accept-ranges",
  "x-content-sha256",
] as const;

async function stream(
  request: Request,
  context: Context,
  bearer: string,
): Promise<Response> {
  const { id } = await context.params;

  const headers: Record<string, string> = {
    Authorization: `Bearer ${bearer}`,
    Accept: "application/octet-stream",
  };
  // The browser's own range request, forwarded verbatim. This is the whole reason
  // the route exists.
  const range = request.headers.get("range");
  if (range) headers.Range = range;

  const upstream = await fetch(`${apiBaseUrl()}/api/v1/media/${encodeURIComponent(id)}/content`, {
    method: "GET",
    headers,
    cache: "no-store",
  });

  const out: Record<string, string> = { "Cache-Control": "no-store" };
  for (const name of PASSTHROUGH) {
    const value = upstream.headers.get(name);
    if (value) out[name] = value;
  }

  /*
    The status is copied rather than assumed: a `206` must reach the player as a
    `206`, and a `416` must reach it as a `416` instead of an empty `200` that
    looks like a zero-length video.
  */
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export async function GET(request: Request, context: Context): Promise<Response> {
  const token = await readAccessToken();
  if (!token) {
    return NextResponse.json(
      { error: { message: "Sesión no iniciada." } },
      { status: 401 },
    );
  }

  const response = await stream(request, context, token);

  /*
    A token can lapse between the render and the play, exactly as it can between a
    render and a click. The renewed token is used directly: re-reading the cookie
    jar here would hand back the one just replaced.
  */
  if (response.status === 401) {
    const renewed = await refreshSession();
    if (renewed) return stream(request, context, renewed);
  }

  return response;
}
