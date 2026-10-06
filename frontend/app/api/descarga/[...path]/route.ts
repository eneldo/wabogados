/**
 * Authenticated binary download.
 *
 * The token is attached here, server side, and the bytes are streamed back.
 * The alternative — handing the browser a URL with `?access_token=...` — puts a
 * live credential into browser history, into the `Referer` of every outbound
 * request and into the access log of the API. That is not a trade worth making
 * for the convenience of a direct link.
 *
 * The upstream `Content-Disposition` is preserved so the browser keeps the
 * original filename, and `Cache-Control: no-store` keeps case material out of
 * the disk cache of a shared machine.
 */

import { NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/api";
import { readAccessToken, refreshSession } from "@/lib/session";

const ALLOWED_PREFIXES = [
  "/api/v1/evidences/",
  "/api/v1/documents/",
  "/api/v1/messages/attachments/",
] as const;

type Params = { params: Promise<{ path: string[] }> };

export async function GET(request: Request, { params }: Params): Promise<NextResponse> {
  const token = await readAccessToken();
  if (!token) {
    return NextResponse.json(
      { error: { message: "Sesión no iniciada." } },
      { status: 401 },
    );
  }

  const segments = (await params).path;
  const target = `/api/v1/${segments.map(encodeURIComponent).join("/")}`;
  if (!ALLOWED_PREFIXES.some((prefix) => target.startsWith(prefix))) {
    return NextResponse.json(
      { error: { message: "Ruta no permitida." } },
      { status: 403 },
    );
  }

  const endpoint = `${apiBaseUrl()}${target}${new URL(request.url).search}`;

  const call = (bearer: string) =>
    fetch(endpoint, {
      headers: { Authorization: `Bearer ${bearer}` },
      cache: "no-store",
    });

  let upstream = await call(token);
  // Same reason as the proxy: a download attempted after the access token
  // expires must not fail merely because a fresh one was available.
  if (upstream.status === 401) {
    const renewed = await refreshSession();
    if (renewed) upstream = await call(renewed);
  }

  if (!upstream.ok || !upstream.body) {
    const payload = await upstream.text().catch(() => "");
    return new NextResponse(payload || "No se pudo descargar el archivo.", {
      status: upstream.status,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  }

  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/octet-stream",
      "Content-Disposition":
        upstream.headers.get("content-disposition") ?? "attachment",
      "Content-Length": upstream.headers.get("content-length") ?? "",
      "Cache-Control": "no-store, private",
      "X-Content-Type-Options": "nosniff",
    },
  });
}