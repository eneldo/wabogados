"use client";

import { useState } from "react";

import { SiteDialog } from "./site-dialog";
import { CONSULTATION_AREAS } from "@/lib/consultation-areas";

/**
 * The consultation form.
 *
 * It posts to `/api/consultas`, which forwards to the backend, and it shows a
 * success message **only** when the backend answers 201. That is the whole
 * contract of this component: the person is told their request was recorded
 * because a row exists, never because the button was pressed.
 *
 * What it deliberately does not do:
 *
 * - It does not keep a copy. No `localStorage`, no state holding what was typed
 *   after the response arrives.
 * - It does not decide what happens next. The backend acknowledges and the firm
 *   reviews; the wording of the confirmation comes from the API so that the page
 *   cannot promise more than the server promised.
 * - It does not clear the form before it knows the outcome. Somebody who typed a
 *   description of their legal problem and was rate limited still has it.
 */

type Status =
  | { kind: "idle" }
  | { kind: "sending" }
  | { kind: "sent"; reference: string; message: string }
  | { kind: "refused"; message: string }
  | { kind: "failed"; message: string };

type FieldName = "fullName" | "phone" | "email" | "area" | "message" | "consent";
type FieldErrors = Partial<Record<FieldName, string>>;

const CONTACT_PHONE = "+57 312 469 9617";
const CONTACT_PHONE_HREF = "+573124699617";

function validateForm(data: FormData): FieldErrors {
  const errors: FieldErrors = {};
  const fullName = String(data.get("fullName") ?? "").trim();
  const phone = String(data.get("phone") ?? "").trim();
  const email = String(data.get("email") ?? "").trim();
  const area = String(data.get("area") ?? "").trim();
  const message = String(data.get("message") ?? "").trim();
  const consent = data.get("consent") === "on";

  if (!fullName) errors.fullName = "Indique su nombre completo.";
  if (!phone) errors.phone = "Indique un teléfono de contacto.";
  if (!email) {
    errors.email = "Indique su correo electrónico.";
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.email = "Indique un correo electrónico válido.";
  }
  if (!area) errors.area = "Seleccione el área de consulta.";
  if (!message) {
    errors.message = "Describa brevemente su consulta.";
  } else if (message.length < 10) {
    errors.message = "La descripción debe tener al menos 10 caracteres.";
  } else if (message.length > 1500) {
    errors.message = "La descripción no puede superar 1500 caracteres.";
  }
  if (!consent) errors.consent = "Debe autorizar el tratamiento de datos para enviar la solicitud.";

  return errors;
}

export function ContactForm({ requestedArea, areas = CONSULTATION_AREAS }: {
  requestedArea?: string;
  areas?: string[];
}) {
  const options = [...new Set([...areas, "Otra consulta"])];
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [formKey, setFormKey] = useState(0);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (status.kind === "sending") return;

    const data = new FormData(form);
    const errors = validateForm(data);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      setStatus({ kind: "idle" });
      const first = Object.keys(errors)[0] as FieldName | undefined;
      if (first) {
        const el = form.querySelector<HTMLElement>(`[name="${first}"]`);
        el?.focus();
      }
      return;
    }

    setFieldErrors({});
    setStatus({ kind: "sending" });

    try {
      const response = await fetch("/api/consultas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fullName: String(data.get("fullName") ?? "").trim(),
          phone: String(data.get("phone") ?? "").trim(),
          email: String(data.get("email") ?? "").trim(),
          area: String(data.get("area") ?? "").trim(),
          message: String(data.get("message") ?? "").trim(),
          consent: data.get("consent") === "on",
          website: data.get("website") ?? "",
        }),
      });

      const payload: unknown = await response.json().catch(() => null);

      if (response.status === 201) {
        const ack = payload as { reference?: string; message?: string } | null;
        setStatus({
          kind: "sent",
          reference: ack?.reference ?? "",
          message:
            ack?.message ??
            "Su solicitud quedó registrada. El despacho la revisará y le contactará.",
        });
        // Only now, once the row exists, is the form emptied.
        form.reset();
        setFormKey((value) => value + 1);
        return;
      }

      setStatus({
        kind: "refused",
        message:
          response.status === 429
            ? `Ha enviado varias solicitudes en poco tiempo. Inténtelo de nuevo en unos minutos o llámenos al ${CONTACT_PHONE}.`
            : (payload as { error?: { message?: string } } | null)?.error?.message
              ?? `No pudimos registrar la solicitud. Revise los campos e inténtelo de nuevo, o llámenos al ${CONTACT_PHONE}.`,
      });
    } catch {
      setStatus({
        kind: "failed",
        message:
          `No pudimos comunicarnos con el servidor. Sus datos siguen en el formulario: inténtelo de nuevo o llámenos al ${CONTACT_PHONE}.`,
      });
    }
  }

  return (
    <>
      <form
        key={formKey}
        onSubmit={onSubmit}
        noValidate
        className="space-y-4"
      >
        <p className="rounded-card border border-ivory-line bg-ivory-warm px-4 py-3 text-sm text-petrol-soft">
          <strong>Qué ocurre al enviar:</strong> registramos su solicitud y el despacho
          la revisará para contactarle. Si necesita atención inmediata, llámenos al{" "}
          <a
            className="underline decoration-gold decoration-1 underline-offset-4 hover:text-gold-deep"
            href={`tel:${CONTACT_PHONE_HREF}`}
          >
            {CONTACT_PHONE}
          </a>
          .
        </p>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Nombre completo" htmlFor="fullName" error={fieldErrors.fullName}>
            <input
              id="fullName"
              name="fullName"
              autoComplete="name"
              required
              placeholder="¿Cómo podemos llamarle?"
              aria-invalid={fieldErrors.fullName ? true : undefined}
              aria-describedby={fieldErrors.fullName ? "fullName-error" : undefined}
              className="site-input"
            />
          </Field>
          <Field label="Teléfono" htmlFor="phone" error={fieldErrors.phone}>
            <input
              id="phone"
              name="phone"
              type="tel"
              autoComplete="tel"
              required
              placeholder="Su número de contacto"
              aria-invalid={fieldErrors.phone ? true : undefined}
              aria-describedby={fieldErrors.phone ? "phone-error" : undefined}
              className="site-input"
            />
          </Field>
        </div>

        <Field label="Correo electrónico" htmlFor="email" error={fieldErrors.email}>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            placeholder="nombre@correo.com"
            aria-invalid={fieldErrors.email ? true : undefined}
            aria-describedby={fieldErrors.email ? "email-error" : undefined}
            className="site-input"
          />
        </Field>

        <Field label="Área de consulta" htmlFor="area" error={fieldErrors.area}>
          <select
            id="area"
            name="area"
            required
            defaultValue={requestedArea ?? ""}
            aria-invalid={fieldErrors.area ? true : undefined}
            aria-describedby={fieldErrors.area ? "area-error" : undefined}
            className="site-input"
          >
            <option value="">Seleccione un área</option>
            {options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </Field>

        <Field label="¿En qué podemos orientarle?" htmlFor="message" error={fieldErrors.message}>
          <textarea
            id="message"
            name="message"
            required
            minLength={10}
            maxLength={1500}
            rows={4}
            placeholder="Describa brevemente su consulta."
            aria-invalid={fieldErrors.message ? true : undefined}
            aria-describedby={[fieldErrors.message ? "message-error" : null, "message-hint"].filter(Boolean).join(" ")}
            className="site-input resize-y"
          />
          <p id="message-hint" className="mt-1 text-xs text-slate">
            Mínimo 10 y máximo 1500 caracteres.
          </p>
        </Field>

        {/*
          A field a person cannot see, so only something filling in forms
          automatically ever completes it. It is labelled and hidden rather than
          omitted: `display: none` inputs are still submitted, and hiding it from
          assistive technology keeps it out of the form's description.
        */}
        <div className="sr-only" aria-hidden="true">
          <label htmlFor="website">No complete este campo</label>
          <input id="website" name="website" type="text" tabIndex={-1} autoComplete="off" />
        </div>

        <div>
          <label className="flex items-start gap-3 text-sm text-slate">
            <input
              type="checkbox"
              name="consent"
              required
              aria-invalid={fieldErrors.consent ? true : undefined}
              aria-describedby={fieldErrors.consent ? "consent-error consent-hint" : "consent-hint"}
              className="mt-1"
            />
            <span>
              He leído el{" "}
              <button
                type="button"
                onClick={() => setPrivacyOpen(true)}
                className="service-link"
              >
                aviso de privacidad
              </button>{" "}
              y autorizo a WABOGADOS a tratar mis datos para valorar mi consulta.
            </span>
          </label>
          <p id="consent-hint" className="mt-1 ml-7 text-xs text-slate">
            Usaremos sus datos solo para atender esta solicitud; no los cedemos con fines comerciales.
          </p>
          {fieldErrors.consent ? (
            <p id="consent-error" className="mt-1 ml-7 text-xs text-wax-deep" role="alert">
              {fieldErrors.consent}
            </p>
          ) : null}
        </div>

        <button
          type="submit"
          disabled={status.kind === "sending"}
          className="site-btn mt-2 w-full disabled:opacity-60"
        >
          {status.kind === "sending" ? "Enviando…" : "Enviar solicitud"}
          <span aria-hidden="true">↗</span>
        </button>

        <div role="status" aria-live="polite">
          {status.kind === "sent" ? (
            <div className="border border-gold/45 bg-ivory-warm px-4 py-3 text-sm text-petrol-soft">
              <p>
                <strong>Solicitud registrada.</strong> {status.message}
              </p>
              {/*
                The reference is the one thing that proves a row exists. It is a
                UUID, not a sequential number, because a sequential one would
                tell a stranger how many consultations the firm has.
              */}
              {status.reference ? (
                <p className="mt-2 text-xs text-slate">
                  Referencia: <span className="font-mono">{status.reference}</span>
                </p>
              ) : null}
            </div>
          ) : null}

          {status.kind === "refused" || status.kind === "failed" ? (
            <p className="border border-gold/45 bg-ivory-warm px-4 py-3 text-sm text-petrol-soft">
              <strong>No pudimos registrar su solicitud.</strong> {status.message}{" "}
              Sus datos permanecen en el formulario.
            </p>
          ) : null}
        </div>
      </form>

      <SiteDialog
        open={privacyOpen}
        onClose={() => setPrivacyOpen(false)}
        label="Aviso de privacidad"
      >
        <p className="site-eyebrow">Aviso de privacidad</p>
        <h2 className="site-display mt-5 text-2xl sm:text-3xl">
          Qué hacemos con lo que escribe aquí.
        </h2>

        <div className="site-body mt-6 space-y-4">
          <p>
            <strong>Responsable.</strong> WABOGADOS, en Bogotá D.C. Responsable del
            tratamiento: William Andres Ruiz. Puede ejercer sus derechos en el
            Edificio Berna Carrera 9 No. 16-20 Oficina 206, Bogotá, o escribiendo a{" "}
            <a
              className="underline decoration-gold decoration-1 underline-offset-4 hover:text-gold-deep"
              href="mailto:amiabogado@hotmail.com"
            >
              amiabogado@hotmail.com
            </a>
            .
          </p>
          <p>
            <strong>Qué recogemos.</strong> Nombre, teléfono, correo electrónico,
            área de consulta y el texto que usted escriba. No recogemos su
            dirección IP ni datos de navegación en este formulario.
          </p>
          <p>
            <strong>Para qué.</strong> Únicamente para valorar su consulta y
            comunicarnos con usted. No usamos sus datos con fines comerciales ni
            los cedemos a terceros.
          </p>
          <p>
            <strong>Estadísticas de la web.</strong> Los contadores solo conservan
            totales de páginas públicas, navegaciones estimadas, clics en teléfono
            y solicitudes registradas. No reciben el contenido de este formulario
            ni usan cookies o huellas del dispositivo. Se respetan Do Not Track y
            Global Privacy Control para las métricas de navegación.
          </p>
          <p>
            <strong>Cuánto tiempo.</strong> Hasta que su consulta se atienda o se
            descarte. Una vez que el asunto se convierte en un expediente, el
            tratamiento pasa a regirse por la relación de encargo profesional y su
            expediente.
          </p>
          <p>
            <strong>Sus derechos.</strong> Puede conocer, corregir, actualizar y
            solicitar la eliminación de sus datos, y revocar este consentimiento en
            cualquier momento, a través de los canales indicados. La eliminación del
            registro de esta solicitud es real: no queda una copia archivada.
          </p>
          <p>
            <strong>Carácter opcional.</strong> Todos los campos son obligatorios
            porque sin ellos no podemos valorar su consulta.
          </p>
        </div>
      </SiteDialog>
    </>
  );
}

function Field({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={htmlFor}
        className="mb-1.5 block text-xs font-semibold tracking-[0.12em] text-petrol-soft uppercase"
      >
        {label}
      </label>
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} className="mt-1 text-xs text-wax-deep" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
