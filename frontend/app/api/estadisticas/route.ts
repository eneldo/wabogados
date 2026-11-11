import { apiBaseUrl } from "@/lib/api";

const UUID4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const HEADERS = { "Cache-Control": "no-store" };

export async function POST(request: Request): Promise<Response> {
  if (process.env.WEBSITE_ANALYTICS_ENABLED === "false" || request.headers.get("DNT") === "1" ||
      request.headers.get("Sec-GPC") === "1" ||
      /bot|crawler|spider|headless|preview|monitor/i.test(request.headers.get("user-agent") ?? "")) {
    return new Response(null, { status: 204, headers: HEADERS });
  }
  const origin = request.headers.get("origin");
  let sameOrigin = false;
  try { sameOrigin = !!origin && new URL(origin).host === request.headers.get("host"); } catch { /* Refuse malformed origins. */ }
  if (!sameOrigin || request.headers.get("sec-fetch-site") === "cross-site") {
    return new Response(null, { status: 403, headers: HEADERS });
  }

  // Cap the actual stream too: Content-Length can be absent or forged.
  const reader = request.body?.getReader();
  if (!reader) return new Response(null, { status: 400, headers: HEADERS });
  const chunks: Uint8Array[] = [];
  let size = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > 1024) {
      await reader.cancel();
      return new Response(null, { status: 413, headers: HEADERS });
    }
    chunks.push(value);
  }
  let body: Record<string, unknown>;
  try {
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    body = JSON.parse(new TextDecoder().decode(bytes));
    if (!body || Array.isArray(body) || typeof body !== "object") throw new Error("shape");
  } catch { return new Response(null, { status: 400, headers: HEADERS }); }
  if (Object.keys(body).sort().join(",") !== "event_id,kind,path,visitor_id" ||
      typeof body.event_id !== "string" || !UUID4.test(body.event_id) ||
      typeof body.visitor_id !== "string" || !UUID4.test(body.visitor_id) ||
      !["page_view", "phone_click"].includes(String(body.kind)) ||
      typeof body.path !== "string" || body.path.length > 180 ||
      !/^(\/|\/servicios\/[a-z0-9-]+|\/analisis\/[a-z0-9-]+)$/.test(body.path)) {
    return new Response(null, { status: 422, headers: HEADERS });
  }
  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/public/analytics/events`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body), cache: "no-store", signal: AbortSignal.timeout(5000),
    });
    // Never forward credentials, IP, referrer, user agent or arbitrary metadata.
    return new Response(null, { status: response.ok ? 204 : response.status, headers: HEADERS });
  } catch { return new Response(null, { status: 503, headers: HEADERS }); }
}
