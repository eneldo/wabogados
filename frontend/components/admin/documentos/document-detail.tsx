"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { Chip, Field, HashChip, Label } from "@/components/primitives";
import {
  confidentialityLabel,
  confidentialityTone,
  documentStatusLabel,
  documentStatusTone,
  documentTypeLabel,
  formatBytes,
  formatDate,
  formatDateTime,
  shortHash,
  visibilityLabel,
  visibilityTone,
} from "@/lib/format";
import type { DocumentDetail } from "@/lib/types";

/**
 * The document drawer.
 *
 * Fetched when it opens rather than passed down from the list: the version
 * list is the whole point of the panel, and a page of two hundred documents
 * would otherwise ship two hundred version histories nobody opens.
 *
 * It is portalled onto `<body>` on purpose. Every ledger row runs the
 * `row-enter` animation, and an element with a transform is the containing
 * block for its `position: fixed` descendants — without the portal the drawer
 * would open as a box the size of one table row instead of covering the page.
 * Being a direct child of the body costs it the `fixed` positioning to
 * `body > *` in globals.css, which is what the `viewport-overlay` class is for.
 *
 * What it never offers is a delete. A document's life ends at `anulado`, and
 * a version's life ends at being replaced — both remain readable afterwards,
 * which is the difference between a file and a trash can.
 */
export function DocumentDetailDrawer({
  documentId,
  canDownload,
  onClose,
}: {
  documentId: string;
  canDownload: boolean;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const response = await fetch(`/api/proxy/documents/${documentId}`, {
          cache: "no-store",
        });
        if (!response.ok) {
          if (!cancelled) setError("No fue posible cargar el documento.");
          return;
        }
        if (cancelled) return;
        setDetail((await response.json()) as DocumentDetail);
      } catch {
        if (!cancelled) setError("No fue posible cargar el documento.");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [documentId]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const versions = detail?.versions ?? [];
  // Highest number first: the current file is at the top, and the history
  // reads backwards from it.
  const ordered = [...versions].sort((a, b) => b.version_number - a.version_number);

  if (typeof document === "undefined") return null;

  return createPortal(
    <div
      className="viewport-overlay flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-label="Detalle del documento"
    >
      <button
        type="button"
        aria-label="Cerrar"
        onClick={onClose}
        className="absolute inset-0 bg-ink/35 backdrop-blur-[2px]"
      />

      <aside className="rise relative flex h-full w-full max-w-xl flex-col overflow-y-auto border-l border-rule-strong bg-paper shadow-[-20px_0_60px_-30px_rgba(25,27,24,0.6)]">
        <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-rule bg-surface px-6 py-5">
          <div className="min-w-0">
            <Label>{detail ? detail.case_number : "Cargando"}</Label>
            <h2 className="font-display mt-1 text-2xl leading-tight">
              {detail ? detail.title : "Cargando documento…"}
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
                <Chip tone={documentStatusTone(detail.status)}>
                  {documentStatusLabel(detail.status)}
                </Chip>
                <Chip tone={visibilityTone(detail.visibility)}>
                  {visibilityLabel(detail.visibility)}
                </Chip>
                <Chip tone={confidentialityTone(detail.confidentiality)}>
                  {confidentialityLabel(detail.confidentiality)}
                </Chip>
                {detail.legal_hold ? <Chip tone="wax">Retención congelada</Chip> : null}
              </div>
              {detail.description ? (
                <p className="mt-4 text-sm leading-relaxed text-ink-soft">
                  {detail.description}
                </p>
              ) : null}
            </section>

            <section>
              <Label>Ficha</Label>
              <dl className="mt-3 grid grid-cols-2 gap-4">
                <Field label="Tipo">{documentTypeLabel(detail.document_type)}</Field>
                <Field label="Expediente">
                  <a
                    href={`/admin/expedientes/${detail.case_id}`}
                    className="underline-offset-4 hover:underline"
                  >
                    {detail.case_number}
                  </a>
                </Field>
                <Field label="Versiones">
                  <span className="tnum">{detail.version_count}</span>
                </Field>
                <Field label="Creado">{formatDate(detail.created_at)}</Field>
                <Field label="Actualizado">{formatDateTime(detail.updated_at)}</Field>
                <Field label="Congelado">
                  {detail.legal_hold ? "Sí" : "No"}
                </Field>
              </dl>
              {detail.legal_hold && detail.legal_hold_reason ? (
                <p className="mt-3 text-xs leading-relaxed text-ink-muted">
                  {detail.legal_hold_reason}
                </p>
              ) : null}
            </section>

            <section>
              <Label>Versiones</Label>
              {ordered.length > 0 ? (
                <ol className="mt-3">
                  {ordered.map((version) => (
                    <li
                      key={version.id}
                      className="border-b border-rule py-3 last:border-0"
                    >
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <span className="text-sm text-ink">
                          v{version.version_number}
                          {version.is_current ? (
                            <span className="ml-2 text-[0.6875rem] font-semibold uppercase tracking-[0.1em] text-forest">
                              Actual
                            </span>
                          ) : null}
                        </span>
                        <span className="tnum text-xs text-ink-muted">
                          {formatBytes(version.size_bytes)}
                        </span>
                      </div>
                      <p className="mt-0.5 truncate text-xs text-ink-muted">
                        {version.original_name}
                      </p>
                      {version.notes ? (
                        <p className="mt-1 text-xs leading-relaxed text-ink-faint">
                          {version.notes}
                        </p>
                      ) : null}
                      <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
                        <span className="flex items-center gap-2">
                          <HashChip value={version.sha256} short={shortHash(version.sha256)} />
                          <span className="tnum text-xs text-ink-faint">
                            {formatDateTime(version.created_at)}
                          </span>
                        </span>
                        {canDownload ? (
                          <a
                            href={`/api/descarga/documents/${detail.id}/versions/${version.id}/download`}
                            className="rounded-card border border-rule-strong px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.1em] text-ink-muted transition-colors hover:border-wax hover:text-wax"
                          >
                            Descargar
                          </a>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="mt-3 text-sm text-ink-muted">
                  Sin versiones: el documento existe como registro, pero nunca
                  llegó a tener un archivo.
                </p>
              )}
            </section>
          </div>
        ) : null}
      </aside>
    </div>,
    document.body,
  );
}
