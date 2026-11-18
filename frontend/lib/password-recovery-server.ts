import { createHmac } from "node:crypto";
import { isIP } from "node:net";

import { NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/api";
import { clearSession } from "@/lib/session";

const HEADERS = { "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" };
const GENERIC = "Si existe una cuenta habilitada con ese correo, recibirás instrucciones para recuperar tu acceso.";

function failure(status: number, message: string) {
  return NextResponse.json({ error: { message } }, { status, headers: HEADERS });
}

export async function recoveryAvailable(): Promise<boolean> {
  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/auth/password-recovery`, {
      cache: "no-store", signal: AbortSignal.timeout(5000),
    });
    return response.ok && (await response.json()).enabled === true;
  } catch {
    return false;
  }
}

async function boundedJson(request: Request): Promise<Record<string, unknown>> {
  if (!request.headers.get("content-type")?.startsWith("application/json")) throw new Error("json");
  const reader = request.body?.getReader();
  if (!reader) throw new Error("body");
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 4096) { await reader.cancel(); throw new Error("size"); }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const raw: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error("body");
  return raw as Record<string, unknown>;
}

export async function forwardRecovery(request: Request, kind: "forgot" | "reset") {
  const origin = process.env.PASSWORD_RECOVERY_PUBLIC_URL;
  const key = process.env.PASSWORD_RECOVERY_PROXY_KEY;
  if (!origin || !key || key.length < 32) return failure(503, "La recuperación por correo aún no está disponible. Contacte al administrador.");
  // Never trust Host/Origin to construct the destination or recovery email link.
  if (request.headers.get("origin") !== origin.replace(/\/$/, "") || request.headers.get("sec-fetch-site") === "cross-site") {
    return failure(403, "Solicitud no permitida.");
  }
  let raw: Record<string, unknown>;
  try { raw = await boundedJson(request); }
  catch { return failure(400, "No fue posible leer el formulario."); }
  const payload = kind === "forgot"
    ? { email: typeof raw.email === "string" ? raw.email.trim() : "" }
    : { token: raw.token, new_password: raw.new_password, confirm_password: raw.confirm_password };
  const endpoint = `/api/v1/auth/${kind === "forgot" ? "forgot-password" : "reset-password"}`;
  // Only enable an IP header behind an ingress that overwrites it. With direct
  // Next access, one shared budget is safer than trusting caller-supplied XFF.
  const trustedHeader = process.env.PASSWORD_RECOVERY_TRUSTED_IP_HEADER;
  const asserted = trustedHeader ? request.headers.get(trustedHeader)?.trim() : undefined;
  const client = asserted && isIP(asserted) ? asserted : "shared-web";
  const stamp = String(Math.floor(Date.now() / 1000));
  const signature = createHmac("sha256", key).update(`${endpoint}|${stamp}|${client}`).digest("hex");
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${endpoint}`, {
      method: "POST", cache: "no-store", signal: AbortSignal.timeout(12000),
      headers: { "Content-Type": "application/json", Accept: "application/json",
        "X-Recovery-Client": client, "X-Recovery-Time": stamp, "X-Recovery-Signature": signature },
      body: JSON.stringify(payload),
    });
  } catch { return failure(503, "La recuperación no está disponible. Inténtelo más tarde."); }
  if (response.status === 202 && kind === "forgot") {
    return NextResponse.json({ message: GENERIC }, { status: 202, headers: HEADERS });
  }
  if (response.status === 200 && kind === "reset") {
    await clearSession();
    return NextResponse.json({ message: "Contraseña actualizada. Inicie sesión con su nueva contraseña." }, { headers: HEADERS });
  }
  if (response.status === 429) return failure(429, "Demasiadas solicitudes. Inténtelo más tarde.");
  if (response.status === 400) return failure(400, "El enlace no es válido o ha caducado. Solicite uno nuevo.");
  if (response.status === 422) return failure(422, "Revise el correo o los campos de contraseña.");
  return failure(503, "La recuperación no está disponible. Inténtelo más tarde.");
}
