"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import { Button } from "@/components/admin/form-controls";
import { MediaThumb } from "@/components/admin/multimedia/media-thumb";
import { formatBytes } from "@/lib/format";
import type { MediaHistoryEntry, MediaRecord } from "@/lib/types";

/**
 * The detail drawer of a resource: what it is, and the file itself.
 *
 * The player is a plain `<video>` / `<audio>` / `<img>` chosen by the kind the
 * server derived from the bytes. Nothing is transcoded, so the browser plays the
 * original through the streaming route — except for images, which open with the
 * 400 px poster the server derives on upload and only read the original when
 * that poster does not exist (assets from before the generator). The full bytes
 * are one click away through "Abrir en otra pestaña", which is where reading
 * detail belongs anyway.
 *
 * **Confidential material is announced, not hidden.** A confidential recording is
 * still playable: refusing it would make the classification a lock rather than a
 * warning, and locks are what people route around. What the drawer does is say so
 * before the file fills the screen, which is the decision the classification is
 * for.
 */

export function MediaDetail({
  item,
  history,
  canDownload,
  closeHref,
}: {
  item: MediaRecord;
  history: MediaHistoryEntry[];
  canDownload: boolean;
  /** Where closing goes: the same listing without `?recurso=`. */
  closeHref: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") router.push(closeHref);
    };
    document.addEventListener("keydown", onKey);
    panelRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [closeHref, router]);

  const source = `/api/media/${item.id}`;
  const confidential = item.confidentiality === "confidencial";

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="presentation">
      <button
        type="button"
        aria-label="Cerrar la ficha"
        onClick={() => router.push(closeHref)}
        className="absolute inset-0 bg-overlay/70"
      />

      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-label={`Ficha de ${item.title}`}
        className="relative flex h-full w-full max-w-2xl flex-col overflow-y-auto border-l border-rule-strong bg-surface shadow-card outline-none"
      >
        <header className="border-b border-rule px-6 py-5">
          <p className="label-rule">Recurso</p>
          <h2 className="font-display mt-1 text-2xl">{item.title}</h2>
          {item.description ? (
            <p className="mt-2 text-sm leading-relaxed text-ink-muted">{item.description}</p>
          ) : null}
        </header>

        {confidential ? (
          <p className="mx-6 mt-5 rounded-card border border-wax/40 bg-wax-tint px-4 py-3 text-sm text-wax-deep">
            <strong>Material confidencial.</strong> Lo que se reproduce aquí no se
            comparte fuera de la firma.
          </p>
        ) : null}

        <div className="px-6 py-5">
          {item.has_file ? (
            <>
              {item.kind === "video" ? (
                <video
                  controls
                  preload="metadata"
                  playsInline
                  className="w-full rounded-card border border-rule bg-shell"
                  src={source}
                />
              ) : null}

              {item.kind === "audio" ? (
                <audio controls preload="metadata" className="w-full" src={source} />
              ) : null}

              {item.kind === "image" ? (
                <MediaThumb
                  id={item.id}
                  alt={item.title}
                  fallbackSrc={source}
                  className="w-full rounded-card border border-rule"
                />
              ) : null}

              {item.kind === "document" ? (
                <p className="rounded-card border border-rule bg-surface-sunk px-4 py-3 text-sm text-ink-muted">
                  Un {item.mime_type === "application/pdf" ? "PDF" : "documento"} se
                  descarga y se abre aparte: el navegador no lo muestra incrustado
                  porque el archivo se sirve con un tipo detectado, no elegido.
                </p>
              ) : null}
            </>
          ) : (
            <p className="rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
              Este recurso está registrado pero no tiene archivo. Es un estado
              normal: se registra lo que se va a recibir y el archivo llega después.
            </p>
          )}

          <dl className="mt-6 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
            <Field label="Archivo" value={item.original_filename ?? "—"} mono />
            <Field label="Tipo" value={item.mime_type ?? "—"} mono />
            <Field
              label="Tamaño"
              value={item.size_bytes === null ? "—" : formatBytes(item.size_bytes)}
            />
            <Field label="Expediente" value={item.case_number ?? "Sin expediente"} />
            <Field label="Etiquetas" value={item.tags ?? "—"} />
            <Field label="Alta" value={new Date(item.created_at).toLocaleString("es-CO")} />
          </dl>

          {item.sha256 ? (
            <p className="mt-4 break-all font-mono text-[0.6875rem] text-ink-faint">
              SHA-256 {item.sha256}
            </p>
          ) : null}

          {canDownload ? (
            <div className="mt-5">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  window.open(source, "_blank", "noopener");
                }}
              >
                Abrir en otra pestaña
              </Button>
            </div>
          ) : null}
        </div>

        <section className="border-t border-rule px-6 py-5">
          <h3 className="label-rule">Historial</h3>
          {history.length === 0 ? (
            <p className="mt-2 text-sm text-ink-muted">Sin cambios registrados.</p>
          ) : (
            <ul className="mt-3 space-y-2 text-sm">
              {history.map((entry, index) => (
                <li key={`${entry.field_name}-${index}`} className="flex gap-3">
                  <span className="w-28 shrink-0 font-mono text-[0.6875rem] text-ink-faint">
                    {entry.field_name}
                  </span>
                  <span className="text-ink-muted">
                    <span className="line-through decoration-rule-strong">{entry.old_value ?? "—"}</span>{" "}
                    → <span className="text-ink">{entry.new_value ?? "—"}</span>
                    {entry.change_reason ? (
                      <span className="block text-xs text-ink-faint">{entry.change_reason}</span>
                    ) : null}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="label-rule">{label}</dt>
      <dd className={`mt-1 break-words text-ink ${mono ? "font-mono text-[0.8125rem]" : ""}`}>
        {value}
      </dd>
    </div>
  );
}
