import { NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/api";
import { clearSession, writeSession } from "@/lib/session";

type LoginBody = { email?: unknown; password?: unknown };

/**
 * Sign in.
 *
 * The response tells the browser *where to go*, computed from the roles and
 * permissions the API just returned. Sending a client to the firm-wide case
 * book, or a lawyer to a client's single file, would contradict what the
 * public site promises and would show a page with nothing on it.
 */
export async function POST(request: Request): Promise<NextResponse> {
  let body: LoginBody;
  try {
    body = (await request.json()) as LoginBody;
  } catch {
    return NextResponse.json(
      { error: { message: "No se pudo leer el formulario." } },
      { status: 400 },
    );
  }

  const email = typeof body.email === "string" ? body.email.trim() : "";
  const password = typeof body.password === "string" ? body.password : "";
  if (!email || !password) {
    return NextResponse.json(
      { error: { message: "Introduce correo y contraseña." } },
      { status: 422 },
    );
  }

  const upstream = await fetch(`${apiBaseUrl()}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ email, password }),
    cache: "no-store",
  });

  if (!upstream.ok) {
    // The backend already says "Credenciales inválidas". Repeating that is
    // better than adding a second, vaguer message.
    const payload = (await upstream.json().catch(() => null)) as {
      error?: { message?: string };
    } | null;
    return NextResponse.json(
      { error: { message: payload?.error?.message ?? "No fue posible iniciar sesión." } },
      { status: upstream.status },
    );
  }

  const tokens = (await upstream.json()) as {
    access_token?: string;
    refresh_token?: string;
  };
  if (!tokens.access_token || !tokens.refresh_token) {
    return NextResponse.json(
      { error: { message: "La sesión no se pudo iniciar." } },
      { status: 502 },
    );
  }

  await writeSession({
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
  });

  const identity = await describeCaller(tokens.access_token);

  return NextResponse.json({ ok: true, ...identity });
}

/**
 * Read the roles and permissions of whoever just signed in, then drop the
 * credential we no longer need from the response path.
 */
async function describeCaller(
  accessToken: string,
): Promise<{ href: string; label: string }> {
  const headers = { Authorization: `Bearer ${accessToken}`, Accept: "application/json" };

  const [rolesResponse, permissionsResponse] = await Promise.all([
    fetch(`${apiBaseUrl()}/api/v1/auth/me/roles`, { headers, cache: "no-store" }),
    fetch(`${apiBaseUrl()}/api/v1/auth/me/permissions`, { headers, cache: "no-store" }),
  ]);

  const roles = rolesResponse.ok ? ((await rolesResponse.json()) as string[]) : [];
  const permissions = permissionsResponse.ok
    ? ((await permissionsResponse.json()) as string[])
    : [];

  const { landingFor } = await import("@/lib/landing");
  return landingFor(roles, permissions);
}

export async function DELETE(): Promise<NextResponse> {
  await clearSession();
  return NextResponse.json({ ok: true });
}
