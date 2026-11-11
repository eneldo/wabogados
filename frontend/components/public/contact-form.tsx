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

export function ContactForm({ requestedArea, areas = CONSULTATION_AREAS }: {
  requestedArea?: string;
  areas?: string[];
}) {
  const options = [...new Set([...areas, "Otra consulta"])];
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [formKey, setFormKey] = useState(0);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (status.kind === "sending") return;

    const data = new FormData(form);
    setStatus({ kind: "sending" });

    try {
      const response = await fetch("/api/consultas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fullName: data.get("fullName") ?? "",
          phone: data.get("phone") ?? "",
          email: data.get("email") ?? "",
          area: data.get("area") ?? "",
          message: data.get("message") ?? "",
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
            ? "Ha enviado varias solicitudes en poco tiempo. Inténtelo de nuevo en unos minutos o llámenos al +57 312 469 9617."
            : (payload as { error?: { message?: string } } | null)?.error?.message
              ?? "No pudimos registrar la solicitud. Revise los campos e inténtelo de nuevo, o llámenos.",
      });
    } catch {
      setStatus({
        kind: "failed",
        message:
          "No pudimos comunicarnos con el servidor. Sus datos siguen en el formulario: inténtelo de nuevo.",
      });
    }
  }

  return (
    <>
      <form
        key={formKey}
        onSubmit={onSubmit}
        noValidate={false}
        className="space-y-4"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Nombre completo" htmlFor="fullName">
            <input
              id="fullName"
              name="fullName"
              autoComplete="name"
              required
              placeholder="¿Cómo podemos llamarle?"
              className="site-input"
            />
          </Field>
          <Field label="Teléfono" htmlFor="phone">
            <input
              id="phone"
              name="phone"
              type="tel"
              autoComplete="tel"
              required
              placeholder="Su número de contacto"
              className="site-input"
            />
          </Field>
        </div>

        <Field label="Correo electrónico" htmlFor="email">
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            placeholder="nombre@correo.com"
            className="site-input"
          />
        </Field>

        <Field label="Área de consulta" htmlFor="area">
          <select
            id="area"
            name="area"
            required
            defaultValue={requestedArea ?? ""}
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

        <Field label="¿En qué podemos orientarle?" htmlFor="message">
          <textarea
            id="message"
            name="message"
            required
            minLength={10}
            maxLength={1500}
            rows={4}
            placeholder="Describa brevemente su consulta."
            className="site-input resize-y"
          />
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

        <label className="flex items-start gap-3 text-sm text-slate">
          <input type="checkbox" name="consent" required className="mt-1" />
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
              <strong>No pudimos registrar su solicitud.</strong> {status.message}
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
            <strong>Responsable.</strong> WABOGADOS, en Bogotá D.C. La razón social
            completa está pendiente de confirmación por la firma. Puede ejercer sus
            derechos escribiendo a la dirección de la oficina indicada en esta
            página.
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
            cualquier momento, escribiendo a la oficina. La eliminación del registro
            de esta solicitud es real: no queda una copia archivada.
          </p>
          <p>
            <strong>Carácter opcional.</strong> Todos los campos son obligatorios
            porque sin ellos no podemos valorar su consulta.
          </p>
        </div>

        <p className="site-note mt-7">
          <span className="pending-tag mr-3">Pendiente de revisión</span>
          Este aviso se redactó con la información que la firma publica en su sitio
          —razón social, dirección y teléfono— y <strong>falta que el despacho lo
          revise y lo apruebe</strong> antes de que la web esté en producción. En
          particular están sin confirmar el canal de contacto para ejercer los
          derechos y el nombre del responsable del tratamiento.
        </p>
      </SiteDialog>
    </>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
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
    </div>
  );
}
