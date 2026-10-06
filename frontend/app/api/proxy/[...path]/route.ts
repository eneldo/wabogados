/**
 * Authenticated proxy for client components.
 *
 * The interactive parts of the interface — dragging a file in, marking a
 * conversation read, acknowledging a deadline — need to call the API from the
 * browser. Rather than hand the browser a token, those calls go through this
 * route, which attaches the credential server side.
 *
 * Deliberately narrow. Only the path prefix and the verbs the interface needs
 * are allowed, so this cannot become a general-purpose hole into the API for
 * anyone who can reach the Next server.
 */

import { NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/api";
import { readAccessToken, refreshSession } from "@/lib/session";

/** Path prefixes a client component is allowed to reach. */
const ALLOWED_PREFIXES = [
  "/api/v1/cases/",
  "/api/v1/evidences",
  "/api/v1/documents/",
  "/api/v1/conversations",
  "/api/v1/notifications",
  "/api/v1/messages/",
] as const;

const ALLOWED_METHODS = new Set(["GET", "POST", "PATCH", "PUT", "DELETE"]);

type Params = { params: Promise<{ path: string[] }> };

function isAllowed(target: string): boolean {
  return ALLOWED_PREFIXES.some((prefix) => target.startsWith(prefix));
}

async function forward(
  request: Request,
  { params }: Params,
  body: BodyInit | null,
): Promise<NextResponse> {
  const method = request.method.toUpperCase();
  if (!ALLOWED_METHODS.has(method)) {
    return NextResponse.json(
      { error: { message: "Método no permitido." } },
      { status: 405 },
    );
  }

  const token = await readAccessToken();
  if (!token) {
    return NextResponse.json(
      { error: { message: "Sesión no iniciada." } },
      { status: 401 },
    );
  }

  const segments = (await params).path;
  const target = `/api/v1/${segments.map(encodeURIComponent).join("/")}`;
  if (!isAllowed(target)) {
    return NextResponse.json(
      { error: { message: "Ruta no permitida." } },
      { status: 403 },
    );
  }

  // The incoming query string is forwarded as-is. It carries filters, never
  // credentials, because credentials live in the cookie and are not in the URL.
  const incoming = new URL(request.url).search;

  const buildHeaders = (bearer: string): Record<string, string> => {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${bearer}`,
      Accept: request.headers.get("accept") ?? "application/json",
    };
    // Let the browser tell the API what filename the upload should carry.
    const contentType = request.headers.get("content-type");
    if (contentType) headers["Content-Type"] = contentType;
    return headers;
  };

  const call = (bearer: string) =>
    fetch(`${apiBaseUrl()}${target}${incoming}`, {
      method,
      headers: buildHeaders(bearer),
      ...(body ? { body } : {}),
      cache: "no-store",
    });

  let upstream = await call(token);

  /*
   * A token can lapse between the render and the click, so the interactive
   * calls renew too. The value returned by the refresh is used directly:
   * re-reading the cookie jar here would hand back the token just replaced.
   */
  if (upstream.status === 401) {
    const renewed = await refreshSession();
    if (renewed) upstream = await call(renewed);
  }

  const payload = await upstream.text();
  const contentTypeUpstream = upstream.headers.get("content-type") ?? "application/json";

  return new NextResponse(payload, {
    status: upstream.status,
    headers: {
      "Content-Type": contentTypeUpstream,
      "Cache-Control": "no-store",
    },
  });
}

export async function GET(request: Request, context: Params): Promise<NextResponse> {
  return forward(request, context, null);
}

export async function POST(request: Request, context: Params): Promise<NextResponse> {
  return forward(request, context, await request.arrayBuffer());
}

export async function PATCH(request: Request, context: Params): Promise<NextResponse> {
  return forward(request, context, await request.arrayBuffer());
}

export async function PUT(request: Request, context: Params): Promise<NextResponse> {
  return forward(request, context, await request.arrayBuffer());
}

export async function DELETE(request: Request, context: Params): Promise<NextResponse> {
  return forward(request, context, null);
}
