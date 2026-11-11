"use client";

import { useEffect, useState } from "react";

import { Chip, Field, Label } from "@/components/primitives";
import {
  evidenceStatusLabel,
  evidenceStatusTone,
  evidenceTypeLabel,
  formatBytes,
  formatDateTime,
  formatPercent,
  visibilityLabel,
  visibilityTone,
} from "@/lib/format";
import type { Custody, EvidenceDetail } from "@/lib/types";

/**
 * The custody drawer.
 *
 * A chain of custody is read as a narrative, so it is laid out as one: a
 * vertical rail of events, each with the moment it happened and who did it. The
 * hash of the original sits at the top, unchanging, because that is the thing
 * every entry below it is measured against.
 *
 * The parent passes a `key` of the evidence id, so opening a different evidence
 * remounts this component with empty state. Resetting the state inside the
 * effect instead would mean a synchronous `setState` during render's commit
 * phase, which cascades an extra render on every open.
 */
export function CustodyDrawer({
  evidenceId,
  onClose,
}: {
  evidenceId: string;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<EvidenceDetail | null>(null);
  const [custody, setCustody] = useState<Custody | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const [detailResponse, custodyResponse] = await Promise.all([
          fetch(`/api/proxy/evidences/${evidenceId}`, { cache: "no-store" }),
          fetch(`/api/proxy/evidences/${evidenceId}/custody`, { cache: "no-store" }),
        ]);
        if (!detailResponse.ok) {
          if (!cancelled) setError("No fue posible cargar la evidencia.");
          return;
        }
        if (cancelled) return;
        setDetail((await detailResponse.json()) as EvidenceDetail);
        if (custodyResponse.ok) {
          setCustody((await custodyResponse.json()) as Custody);
        }
      } catch {
        if (!cancelled) setError("No fue posible cargar la evidencia.");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [evidenceId]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const original = detail?.files.find((item) => item.is_original) ?? detail?.files[0];
  const derivatives = detail?.derivatives ?? [];
  const optimised = derivatives.reduce((sum, item) => sum + (item.size_bytes ?? 0), 0);
  const hasDerivatives = derivatives.length > 0;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-label="Cadena de custodia"
    >
      <button
        type="button"
        aria-label="Cerrar"
        onClick={onClose}
        className="absolute inset-0 bg-overlay/70 backdrop-blur-[2px]"
      />

      <aside className="rise relative flex h-full w-full max-w-xl flex-col overflow-y-auto border-l border-rule-strong bg-canvas shadow-[-20px_0_60px_-30px_rgba(25,27,24,0.6)]">
        <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-rule bg-surface px-6 py-5">
          <div className="min-w-0">
            <Label>{detail ? detail.case_number : "Cargando"}</Label>
            <h2 className="font-display mt-1 text-2xl leading-tight">
              {detail ? detail.title : "Cargando evidencia…"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-card border border-rule-strong px-2.5 py-1.5 text-xs font-semibold uppercase tracking-wider text-ink-muted transition-colors hover:border-wax hover:text-wax"
          >
            Cerrar
          </button>
        </header>

        {error ? (
          <p className="m-6 rounded-card border border-wax/30 bg-wax-tint px-4 py-3 text-sm text-wax-deep">
            {error}
          </p>
        ) : null}

        {detail ? (
          <div className="space-y-8 px-6 py-6">
            <section>
              <div className="flex flex-wrap items-center gap-2">
                <Chip tone={evidenceStatusTone(detail.status)}>
                  {evidenceStatusLabel(detail.status)}
                </Chip>
                <Chip tone={visibilityTone(detail.visibility)}>
                  {visibilityLabel(detail.visibility)}
                </Chip>
                {detail.is_signed_pdf ? (
                  <Chip tone="brass">PDF con firma digital</Chip>
                ) : null}
              </div>
              {detail.description ? (
                <p className="mt-4 text-sm leading-relaxed text-ink-soft">
                  {detail.description}
                </p>
              ) : null}
            </section>

            <section>
              <Label>Integridad del original</Label>
              {detail.original_sha256 ? (
                <div className="stamp mt-3 rounded-card border border-forest/25 bg-forest-tint px-4 py-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.1em] text-forest">
                    SHA-256 registrado
                  </p>
                  <p className="tnum mt-1.5 break-all text-sm text-forest">
                    {detail.original_sha256}
                  </p>
                  <p className="mt-2 text-xs text-forest/80">
                    Este valor no cambia. Si el archivo descargado no produce el
                    mismo hash, no es el archivo que se registró.
                  </p>
                </div>
              ) : (
                /*
                  No hash means no original was ever stored — the file was
                  refused before it could become evidence. Showing this in the
                  green "registered" box would assert a verification that never
                  happened, which is the one thing an integrity panel must not do.
                */
                <div className="mt-3 rounded-card border border-brass/30 bg-brass-tint px-4 py-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.1em] text-brass">
                    Sin original almacenado
                  </p>
                  <p className="mt-1.5 text-sm text-brass">
                    No hay hash porque el archivo no llegó a almacenarse. La
                    evidencia existe como registro, pero no contiene prueba.
                  </p>
                </div>
              )}
            </section>

            <section>
              <Label>Ficha</Label>
              <dl className="mt-3 grid grid-cols-2 gap-4">
                <Field label="Tipo">{evidenceTypeLabel(detail.evidence_type)}</Field>
                <Field label="Archivo">
                  <span className="tnum block truncate text-sm">
                    {detail.original_filename ?? "sin archivo"}
                  </span>
                </Field>
                <Field label="Peso original">
                  {formatBytes(original?.file_size ?? detail.original_size)}
                </Field>
                <Field label="Peso optimizado">
                  {hasDerivatives ? formatBytes(optimised) : "—"}
                </Field>
                <Field label="Reducción">{reductionOf(original?.file_size, optimised, hasDerivatives)}</Field>
                <Field label="Páginas">
                  {original?.page_count ?? "—"}
                </Field>
                <Field label="Captura">
                  {detail.captured_at ? formatDateTime(detail.captured_at) : "—"}
                </Field>
                <Field label="Lugar de captura">
                  {detail.captured_location ?? "—"}
                </Field>
              </dl>
            </section>

            {hasDerivatives ? (
              <section>
                <Label>Derivados</Label>
                <ul className="ledger mt-3">
                  {derivatives.map((item) => (
                    <li key={item.id} className="py-2.5">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <span className="text-sm text-ink">{item.derivative_type}</span>
                        <span className="tnum text-xs text-ink-muted">
                          {formatBytes(item.size_bytes)}
                        </span>
                      </div>
                      {item.compression_ratio !== null ? (
                        <p className="tnum mt-0.5 text-xs text-forest">
                          {savingSentence(item.compression_ratio)}
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {original ? (
              <section>
                <a
                  href={`/api/descarga/evidences/${detail.id}/original`}
                  className="inline-flex items-center gap-2 rounded-card bg-action px-4 py-2.5 text-sm font-semibold text-on-action transition-colors hover:bg-action-hover"
                >
                  Descargar original
                </a>
                <p className="mt-2 text-xs text-ink-faint">
                  La descarga queda registrada en la cadena de custodia.
                </p>
              </section>
            ) : null}

            <section>
              <Label>Cadena de custodia</Label>
              {custody && custody.events.length > 0 ? (
                <ol className="mt-4 space-y-0">
                  {custody.events.map((event, index) => (
                    <li key={event.id} className="relative flex gap-4 pb-6 last:pb-0">
                      {index < custody.events.length - 1 ? (
                        <span
                          aria-hidden="true"
                          className="absolute top-3 left-[5px] h-full w-px bg-rule-strong"
                        />
                      ) : null}
                      <span
                        aria-hidden="true"
                        className="relative mt-1.5 size-2.5 shrink-0 rounded-full border-2 border-wax bg-canvas"
                      />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-ink">
                          {eventLabel(event.event_type)}
                        </p>
                        {event.detail ? (
                          <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">
                            {event.detail}
                          </p>
                        ) : null}
                        <p className="tnum mt-1 text-xs text-ink-faint">
                          {formatDateTime(event.created_at)}
                          {event.ip_address ? ` · ${event.ip_address}` : ""}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="mt-3 text-sm text-ink-muted">
                  Sin eventos registrados todavía.
                </p>
              )}
            </section>

            {custody && custody.accesses.length > 0 ? (
              <section>
                <Label>Accesos</Label>
                <ul className="mt-3 space-y-2">
                  {custody.accesses.slice(0, 8).map((access) => (
                    <li
                      key={access.id}
                      className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule pb-2 last:border-0"
                    >
                      <span className="text-sm text-ink">
                        {accessLabel(access.access_type)}
                      </span>
                      <span className="tnum text-xs text-ink-faint">
                        {formatDateTime(access.created_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
        ) : null}
      </aside>
    </div>
  );
}

const EVENT_LABELS: Record<string, string> = {
  uploaded: "Archivo recibido",
  validated: "Validación superada",
  original_stored: "Original almacenado",
  derivative_created: "Derivado creado",
  processed: "Procesado completo",
  processing_failed: "El procesado falló",
  queued: "Procesado en cola",
  visibility_changed: "Visibilidad modificada",
  classified: "Clasificada",
  archived: "Archivada",
  downloaded_original: "Original descargado",
  downloaded_derivative: "Derivado descargado",
  viewed: "Vista previa consultada",
  message_sent: "Mensaje enviado",
};

function eventLabel(eventType: string): string {
  return EVENT_LABELS[eventType] ?? eventType;
}

const ACCESS_LABELS: Record<string, string> = {
  view: "Vista previa",
  download_original: "Descarga del original",
  download_derivative: "Descarga de derivado",
};

function accessLabel(accessType: string): string {
  return ACCESS_LABELS[accessType] ?? accessType;
}


/**
 * Reduction of the derivative set against the original.
 *
 * Three outcomes, kept apart on purpose: no original, nothing to compare, and
 * a derivative set that weighs more than the file it came from. Clamping the
 * last case to `0 %` and printing it as a saving would be a false statement in
 * a document about evidence.
 */
function reductionOf(
  originalBytes: number | undefined,
  optimisedBytes: number,
  hasDerivatives: boolean,
) {
  if (!originalBytes || !hasDerivatives) return "—";
  if (optimisedBytes > originalBytes) return "mayor que el original";
  if (optimisedBytes === originalBytes) return "sin cambio";
  return formatPercent(((originalBytes - optimisedBytes) / originalBytes) * 100);
}

/**
 * The backend's `compression_ratio` is already a percentage, so it must not be
 * scaled again. A negative value means the derivative grew, and calling that a
 * compression would invert the meaning.
 */
function savingSentence(ratio: number): string {
  if (ratio < 0) return `${formatPercent(Math.abs(ratio))} más grande que el original`;
  if (ratio === 0) return "mismo tamaño que el original";
  return `${formatPercent(ratio)} de reducción`;
}
