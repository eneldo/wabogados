"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Button, FormField, TextInput } from "@/components/admin/form-controls";

const UNAVAILABLE = "La recuperación por correo aún no está disponible. Contacte al administrador.";

async function post(path: string, data: Record<string, string>) {
  const response = await fetch(path, { method: "POST", cache: "no-store",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
  const payload = await response.json();
  return { ok: response.ok, status: response.status, message: payload.message ?? payload.error?.message ?? "No fue posible completar la solicitud." };
}

export function ForgotPasswordForm({ enabled }: { enabled: boolean }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const guard = useRef(false);

  if (!enabled) return <p role="status" className="text-sm text-brass">{UNAVAILABLE}</p>;
  return (
    <form noValidate className="space-y-4" onSubmit={async (event) => {
      event.preventDefault();
      if (guard.current) return;
      const form = event.currentTarget;
      const input = form.querySelector<HTMLInputElement>('input[name="email"]');
      const email = String(new FormData(form).get("email") ?? "").trim();
      setError(""); setMessage("");
      if (!email || !input?.validity.valid) { setError("Introduzca un correo válido."); input?.focus(); return; }
      guard.current = true; setBusy(true);
      try {
        const result = await post("/api/recuperacion/solicitar", { email });
        if (result.ok && result.status === 202) { setMessage(result.message); form.reset(); }
        else { setError(result.message); input?.focus(); }
      } catch { setError("No fue posible conectar. Inténtelo más tarde."); }
      finally { guard.current = false; setBusy(false); }
    }}>
      <p className="text-sm text-ink-soft">Escriba su correo registrado. Le enviaremos instrucciones si la cuenta está habilitada.</p>
      <FormField label="Correo electrónico" name="email" idPrefix="recuperar" required error={error || undefined}>
        {(props) => <TextInput {...props} type="email" autoComplete="email" required maxLength={255} disabled={busy} />}
      </FormField>
      <p role="status" aria-live="polite" className="text-sm text-forest">{message}</p>
      <Button type="submit" variant="primary" disabled={busy}>{busy ? "Enviando solicitud…" : "Enviar instrucciones"}</Button>
    </form>
  );
}

export function ResetPasswordForm({ enabled }: { enabled: boolean }) {
  const [token, setToken] = useState<string | null>(null);
  const initialToken = useRef<string | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [visible, setVisible] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [success, setSuccess] = useState(false);
  const guard = useRef(false);
  const form = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (initialToken.current === undefined) {
      const candidate = new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
      initialToken.current = /^[A-Za-z0-9_-]{43}$/.test(candidate) ? candidate : "";
      window.history.replaceState(null, "", window.location.pathname);
    }
    // Retain only in memory. A ref keeps Strict Mode's effect replay from
    // replacing the initial fragment with the now-sanitised empty URL.
    queueMicrotask(() => setToken(initialToken.current ?? ""));
  }, []);

  useEffect(() => {
    form.current?.querySelector<HTMLInputElement>('[aria-invalid="true"]')?.focus();
  }, [errors]);

  if (!enabled) return <p role="status" className="text-sm text-brass">{UNAVAILABLE}</p>;
  if (success) return <p role="status" className="text-sm text-forest">{message}</p>;
  if (token === null) return <p role="status" className="text-sm text-ink-muted">Comprobando enlace…</p>;
  if (!token) return <div><p role="alert" className="text-sm text-brass">El enlace no es válido o ha caducado. Reabra el correo o solicite uno nuevo.</p><Link href="/olvide-contrasena" className="mt-4 inline-block text-sm underline">Solicitar un nuevo enlace</Link></div>;

  return (
    <form ref={form} noValidate className="space-y-4" aria-busy={busy} onSubmit={async (event) => {
      event.preventDefault();
      if (guard.current) return;
      const fields = new FormData(event.currentTarget);
      const password = String(fields.get("new_password") ?? "");
      const confirmation = String(fields.get("confirm_password") ?? "");
      const next: Record<string, string> = {};
      if (Array.from(password).length < 8 || Array.from(password).length > 128) next.new_password = "Use entre 8 y 128 caracteres.";
      if (password !== confirmation) next.confirm_password = "Las contraseñas no coinciden.";
      setErrors(next); setMessage("");
      if (Object.keys(next).length) return;
      guard.current = true; setBusy(true);
      try {
        const result = await post("/api/recuperacion/restablecer", { token, new_password: password, confirm_password: confirmation });
        form.current?.reset();
        setMessage(result.message);
        if (result.ok) { setToken(""); initialToken.current = ""; setSuccess(true); }
        else if (result.status === 400) { setToken(""); initialToken.current = ""; }
      } catch { setMessage("No fue posible conectar. Inténtelo más tarde."); form.current?.reset(); }
      finally { guard.current = false; setBusy(false); }
    }}>
      <p className="text-sm text-ink-soft">Elija una nueva contraseña. Se cerrarán todas las sesiones anteriores de su cuenta.</p>
      <fieldset disabled={busy} className="space-y-4">
        <FormField label="Nueva contraseña" name="new_password" idPrefix="restablecer" required error={errors.new_password} hint="Entre 8 y 128 caracteres. Los espacios se conservan.">
          {(props) => <TextInput {...props} type={visible ? "text" : "password"} autoComplete="new-password" required minLength={8} maxLength={128} />}
        </FormField>
        <FormField label="Confirmar contraseña" name="confirm_password" idPrefix="restablecer" required error={errors.confirm_password}>
          {(props) => <TextInput {...props} type={visible ? "text" : "password"} autoComplete="new-password" required minLength={8} maxLength={128} />}
        </FormField>
        <Button type="button" variant="ghost" aria-pressed={visible} onClick={() => setVisible(!visible)}>{visible ? "Ocultar contraseñas" : "Mostrar contraseñas"}</Button>
      </fieldset>
      <p role="alert" className="text-sm text-brass">{message}</p>
      <Button type="submit" variant="primary" disabled={busy}>{busy ? "Guardando…" : "Guardar nueva contraseña"}</Button>
    </form>
  );
}
