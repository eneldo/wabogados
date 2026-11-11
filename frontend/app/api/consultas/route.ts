/**
 * Public intake for the consultation form.
 *
 * Separate from `api/proxy/[...path]` on purpose, twice over:
 *
 * 1. The proxy **requires a session**. This form is used by somebody with no
 *    account — that is the whole point of it — so it cannot be an authenticated
 *    call.
 * 2. The proxy allows any verb and any path under a list of prefixes. This route
 *    is one fixed path and one verb, forwards a fixed body shape and nothing
 *    else. A route that forwards whatever it is given is a hole with a rate limit
 *    in front of it.
 *
 * The body is rebuilt field by field instead of being piped through. Anything not
 * named here never leaves the Next server, so a caller cannot smuggle a field the
 * API would have rejected, or one it does not know.
 *
 * The in-memory throttle below is a courtesy, not the control. Every request still
 * crosses the network to the API, which applies its own budget keyed by IP; this
 * one just saves the round trip for the person who presses the button twice.
 */

import { NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/api";
import { CONSULTATION_AREAS, consultationSubject } from "@/lib/consultation-areas";
import { getPublicServices } from "@/lib/public-services.server";

/** Per-IP budget for this route, mirroring the API's own. */
const WINDOW_MS = 60 * 60 * 1000;
const MAX_PER_WINDOW = 3;
const attempts = new Map<string, number[]>();

function throttled(clientKey: string): boolean {
  const now = Date.now();
  for (const [key, times] of attempts) {
    const recent = times.filter((t) => now - t < WINDOW_MS);
    if (recent.length === 0) attempts.delete(key);
    else attempts.set(key, recent);
  }
  const recent = (attempts.get(clientKey) ?? []).filter((t) => now - t < WINDOW_MS);
  if (recent.length >= MAX_PER_WINDOW) return true;
  attempts.set(clientKey, [...recent, now]);
  return false;
}

/** Best-effort client identity: the first entry of `X-Forwarded-For`. */
function clientKey(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0].trim();
  return request.headers.get("x-real-ip") ?? "desconocida";
}

function text(value: unknown, max: number): string {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}

export async function POST(request: Request): Promise<NextResponse> {
  if (throttled(clientKey(request))) {
    return NextResponse.json(
      {
        error: {
          code: "rate_limit_exceeded",
          message:
            "Ha enviado varias solicitudes en poco tiempo. Inténtelo de nuevo en unos minutos o llámenos.",
        },
      },
      { status: 429, headers: { "Cache-Control": "no-store" } },
    );
  }

  let raw: unknown;
  try {
    raw = await request.json();
  } catch {
    return NextResponse.json(
      { error: { code: "invalid_json", message: "No pudimos leer el formulario." } },
      { status: 400, headers: { "Cache-Control": "no-store" } },
    );
  }

  const body = (raw ?? {}) as Record<string, unknown>;
  const selectedArea = typeof body.area === "string" ? body.area : "";
  if (!CONSULTATION_AREAS.includes(selectedArea)) {
    const { services, available } = await getPublicServices();
    if (!available) {
      return NextResponse.json(
        { error: { code: "catalogue_unavailable", message: "No pudimos verificar el área. Inténtelo de nuevo más tarde." } },
        { status: 503, headers: { "Cache-Control": "no-store" } },
      );
    }
    if (!services.some((service) => service.title === selectedArea)) {
      return NextResponse.json(
        { error: { code: "invalid_area", message: "Seleccione un área publicada por el despacho." } },
        { status: 422, headers: { "Cache-Control": "no-store" } },
      );
    }
  }

  // The deployed backend accepts the original seven labels. Route other live
  // areas through its "Otra consulta" option and preserve their exact name in
  // the message; never drop or silently replace the service the visitor chose.
  const message = text(body.message, 1501).replace(/\s+/g, " ");
  if (message.length < 10 || message.length > 1500) {
    return NextResponse.json(
      { error: { code: "invalid_message", message: "Describa su consulta en entre 10 y 1500 caracteres." } },
      { status: 422, headers: { "Cache-Control": "no-store" } },
    );
  }
  const subject = consultationSubject(selectedArea, message);
  if (subject.message.length > 1500) {
    return NextResponse.json(
      { error: { code: "message_too_long", message: "Acorte la consulta para incluir el nombre del área dentro del límite de 1500 caracteres." } },
      { status: 422, headers: { "Cache-Control": "no-store" } },
    );
  }

  // The trap is forwarded untouched. A person's browser leaves it empty, so
  // filling it in is the API's signal to refuse without storing anything.
  const payload = {
    full_name: text(body.fullName, 255),
    phone: text(body.phone, 50),
    email: text(body.email, 320),
    area: subject.area,
    message: subject.message,
    consent: body.consent === true,
    website: text(body.website, 200),
  };

  const upstream = await fetch(`${apiBaseUrl()}/api/v1/consultations`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  }).catch(() => null);

  if (!upstream) {
    return NextResponse.json(
      { error: { code: "service_unavailable", message: "No pudimos comunicarnos con el despacho. Inténtelo de nuevo más tarde." } },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }

  const text_ = await upstream.text();

  return new NextResponse(text_, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
    },
  });
}
