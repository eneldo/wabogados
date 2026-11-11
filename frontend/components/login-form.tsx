"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/**
 * Sign in.
 *
 * A client component only because it has to read the form and post it. The
 * password goes to this app's own `/api/session` route, never to the API
 * directly, so the tokens can be set as `httpOnly` cookies.
 */
export function LoginForm() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Read the submitted DOM, not React's last change event. Autofill and fast
    // entry during navigation can populate fields before those events arrive.
    const fields = new FormData(event.currentTarget);
    const email = String(fields.get("email") ?? "").trim();
    const password = String(fields.get("password") ?? "");
    setError(null);
    setBusy(true);

    try {
      const response = await fetch("/api/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const payload = (await response.json()) as {
        error?: { message?: string };
        href?: string;
      };

      if (!response.ok) {
        setError(payload.error?.message ?? "No fue posible iniciar sesión.");
        return;
      }

      // The server decided the destination from the caller's own permissions.
      // The cookies are set; this re-render is what makes the server read them.
      router.replace(payload.href ?? "/portal");
      router.refresh();
    } catch {
      setError("No se pudo contactar con el servidor.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5">
      <div>
        <label htmlFor="email" className="label-rule block">
          Correo
        </label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="username"
          required
          className="mt-1.5 w-full rounded-card border border-rule-strong bg-surface px-3.5 py-2.5 text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-wax"
          placeholder="nombre@despacho.example"
        />
      </div>

      <div>
        <label htmlFor="password" className="label-rule block">
          Contraseña
        </label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          className="mt-1.5 w-full rounded-card border border-rule-strong bg-surface px-3.5 py-2.5 text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-wax"
        />
      </div>

      {error ? (
        <p
          role="alert"
          className="rise rounded-card border border-wax/30 bg-wax-tint px-3.5 py-2.5 text-sm text-wax-deep"
        >
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={busy}
        className="w-full rounded-card bg-action px-4 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-on-action transition-colors hover:bg-action-hover disabled:cursor-not-allowed disabled:opacity-60"
      >
        {busy ? "Comprobando…" : "Entrar"}
      </button>
    </form>
  );
}
