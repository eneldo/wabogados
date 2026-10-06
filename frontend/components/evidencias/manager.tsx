"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { EmptyState, SectionHeading } from "@/components/primitives";
import { evidenceStatusTone } from "@/lib/format";
import type { Evidence } from "@/lib/types";

import { CustodyDrawer } from "./custody-drawer";
import { EvidenceCard, EvidenceTable } from "./evidence-views";
import { UploadZone } from "./upload-zone";
import { useEvidenceSummaries } from "./use-evidence-summaries";

type View = "tarjetas" | "tabla";
type Filter = "todas" | "recientes" | "publicadas" | "cuarentena";

/**
 * The evidence manager.
 *
 * Section 39 asks for a card view and a table view, and both are here because
 * they answer different questions. This component owns only what the user
 * changes: which view, which filter, and which evidence is open. The list itself
 * arrives from the server already scoped, and the refresh after an upload is a
 * `router.refresh()` so the next render re-reads it.
 */
export function EvidenceManager({
  caseId,
  caseNumber,
  caseTitle,
  initial,
  canUpload,
}: {
  caseId: string;
  caseNumber?: string;
  caseTitle?: string;
  initial: Evidence[];
  canUpload: boolean;
}) {
  const [view, setView] = useState<View>("tarjetas");
  const [filter, setFilter] = useState<Filter>("todas");
  const [inspected, setInspected] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const router = useRouter();

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();

    const matches = initial.filter((item) => {
      if (needle) {
        const haystack = `${item.title} ${item.original_filename ?? ""} ${item.case_number}`.toLowerCase();
        if (!haystack.includes(needle)) return false;
      }
      if (filter === "publicadas" && item.visibility !== "publicada") return false;
      if (filter === "cuarentena") {
        if (evidenceStatusTone(item.status) !== "wax") return false;
      }
      return true;
    });

    if (filter !== "recientes") return matches;

    // "Recientes" is the newest ten, ordered by the creation timestamp the
    // server sent. It deliberately does not compare against the current clock:
    // reading the time during render makes the result depend on when the
    // component happened to re-render, and a lawyer refreshing the page should
    // not see the list change.
    return [...matches]
      .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
      .slice(0, 10);
  }, [filter, initial, query]);

  // Derivative weights are only needed to fill the table's columns.
  const ids = useMemo(() => filtered.map((item) => item.id), [filtered]);
  const summaries = useEvidenceSummaries(ids, view === "tabla");

  const counts = useMemo(
    () => ({
      total: initial.length,
      publicadas: initial.filter((item) => item.visibility === "publicada").length,
      cuarentena: initial.filter(
        (item) => evidenceStatusTone(item.status) === "wax",
      ).length,
    }),
    [initial],
  );

  return (
    <div className="space-y-8">
      <SectionHeading
        eyebrow={caseNumber ? `Expediente ${caseNumber}` : "Expediente"}
        title="Evidencias"
        action={
          <div className="flex items-center gap-4">
            {caseTitle ? (
              <span className="hidden max-w-xs truncate text-sm text-ink-muted sm:inline">
                {caseTitle}
              </span>
            ) : null}
            <div
              className="flex overflow-hidden rounded-card border border-rule-strong"
              role="group"
              aria-label="Cambiar vista"
            >
              {(["tarjetas", "tabla"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setView(option)}
                  aria-pressed={view === option}
                  className={`px-4 py-2 text-xs font-semibold uppercase tracking-[0.1em] transition-colors ${
                    view === option
                      ? "bg-ink text-paper"
                      : "bg-surface text-ink-muted hover:text-ink"
                  }`}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>
        }
      />

      {canUpload ? (
        <section>
          <UploadZone
            caseId={caseId}
            onUploaded={() => router.refresh()}
          />
        </section>
      ) : null}

      <section className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-ink-muted">
            <span>
              <strong className="tnum text-ink">{counts.total}</strong>{" "}
              {counts.total === 1 ? "registrada" : "registradas"}
            </span>
            <span>
              <strong className="tnum text-ink">{counts.publicadas}</strong> publicadas
            </span>
            {counts.cuarentena > 0 ? (
              <span className="text-wax-deep">
                <strong className="tnum">{counts.cuarentena}</strong> en cuarentena
              </span>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <label htmlFor="evidence-search" className="sr-only">
              Buscar evidencia
            </label>
            <input
              id="evidence-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Buscar por título o archivo"
              className="w-56 rounded-card border border-rule-strong bg-surface px-3 py-1.5 text-sm outline-none transition-colors placeholder:text-ink-faint focus:border-wax"
            />

            <div className="flex flex-wrap gap-1.5">
              {(
                [
                  ["todas", "Todas"],
                  ["recientes", "Recientes"],
                  ["publicadas", "Publicadas"],
                  ["cuarentena", "Cuarentena"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setFilter(value)}
                  aria-pressed={filter === value}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                    filter === value
                      ? "bg-wax text-paper"
                      : "bg-paper-deep text-ink-soft hover:bg-rule"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {filtered.length === 0 ? (
          <EmptyState
            title={
              initial.length === 0
                ? "Todavía no hay evidencias"
                : "Ninguna evidencia coincide con el filtro"
            }
            hint={
              initial.length === 0
                ? "Las evidencias que se registren en este expediente aparecerán aquí, con su peso original, sus derivados y su hash."
                : undefined
            }
          />
        ) : view === "tarjetas" ? (
          <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {filtered.map((item) => (
              <EvidenceCard
                key={item.id}
                evidence={item}
                onInspect={setInspected}
              />
            ))}
          </div>
        ) : (
          <EvidenceTable
            evidence={filtered}
            summaries={summaries}
            onInspect={setInspected}
          />
        )}
      </section>

      {inspected ? (
        <CustodyDrawer
          key={inspected}
          evidenceId={inspected}
          onClose={() => setInspected(null)}
        />
      ) : null}
    </div>
  );
}
