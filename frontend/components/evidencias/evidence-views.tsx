"use client";

import { Chip, HashChip } from "@/components/primitives";
import {
  evidenceStatusLabel,
  evidenceStatusTone,
  evidenceTypeLabel,
  formatBytes,
  formatDate,
  formatPercent,
  visibilityLabel,
  visibilityTone,
} from "@/lib/format";
import type { Evidence } from "@/lib/types";

import { EvidenceThumb } from "./evidence-thumb";
import type { DetailSummary } from "./use-evidence-summaries";

/**
 * The two views section 39 asks for, and the fields it lists.
 *
 * Card and table are not two renderings of one thing. The card answers "what is
 * this and does it look right"; the table answers "compare these twenty", which
 * is where the weights and the reduction finally line up in columns.
 *
 * A dash in the table means "not loaded yet", never "zero". Showing 0 for a
 * derivative that has not been measured would be a false statement in a document
 * about evidence.
 */

export function EvidenceCard({
  evidence,
  onInspect,
}: {
  evidence: Evidence;
  onInspect: (id: string) => void;
}) {
  const tone = evidenceStatusTone(evidence.status);

  return (
    <article className="group flex flex-col overflow-hidden rounded-card border border-rule bg-surface transition-all duration-200 hover:-translate-y-0.5 hover:border-rule-strong hover:shadow-[0_10px_26px_-16px_rgba(25,27,24,0.55)]">
      <EvidenceThumb
        evidenceId={evidence.id}
        fileName={evidence.original_filename}
        mimeType={evidence.original_mime_type}
      />

      <div className="flex flex-1 flex-col p-4">
        <div className="flex items-start justify-between gap-2">
          <p className="tnum text-[0.6875rem] text-ink-muted">
            {evidence.case_number}
          </p>
          <Chip tone={tone}>{evidenceStatusLabel(evidence.status)}</Chip>
        </div>

        <h3 className="font-display mt-1.5 text-lg leading-snug text-ink">
          {evidence.title}
        </h3>

        <p className="mt-1 text-xs text-ink-muted">
          {evidenceTypeLabel(evidence.evidence_type)}
          {evidence.is_signed_pdf ? " · PDF firmado" : ""}
        </p>

        <dl className="mt-4 grid grid-cols-2 gap-x-3 gap-y-2.5 border-t border-rule pt-3.5">
          <div>
            <dt className="label-rule">Original</dt>
            <dd className="tnum mt-0.5 text-xs text-ink">
              {formatBytes(evidence.original_size)}
            </dd>
          </div>
          <div>
            <dt className="label-rule">Derivados</dt>
            <dd className="tnum mt-0.5 text-xs text-ink">
              {evidence.derivative_count}
            </dd>
          </div>
          <div>
            <dt className="label-rule">Fecha</dt>
            <dd className="mt-0.5 text-xs text-ink">
              {formatDate(evidence.captured_at ?? evidence.created_at)}
            </dd>
          </div>
          <div>
            <dt className="label-rule">Visibilidad</dt>
            <dd className="mt-0.5">
              <Chip tone={visibilityTone(evidence.visibility)}>
                {visibilityLabel(evidence.visibility)}
              </Chip>
            </dd>
          </div>
        </dl>

        <div className="mt-4 flex items-center justify-between gap-2 border-t border-rule pt-3.5">
          <HashChip value={evidence.original_sha256} tone={tone} />
          <button
            type="button"
            onClick={() => onInspect(evidence.id)}
            className="text-xs font-semibold uppercase tracking-[0.1em] text-wax underline-offset-4 transition-colors hover:underline"
          >
            Custodia
          </button>
        </div>
      </div>
    </article>
  );
}

/**
 * The reduction cell.
 *
 * Three outcomes, and conflating them would misreport the record:
 *
 *   not measured yet   a dash: the details have not loaded
 *   no derivatives     a dash: there is nothing to compare against
 *   equal in size      "sin cambio": zero is a true saving of nothing
 *   larger than before "mayor", never "0 %": clamping a negative to zero and
 *                      printing it as a saving would be a false statement in a
 *                      document about evidence
 */
function reductionView(
  item: Evidence,
  summary: DetailSummary | undefined,
) {
  const hasDerivatives = (summary?.derivativeCount ?? item.derivative_count) > 0;
  if (!summary || !hasDerivatives) {
    return <span className="text-ink-faint">—</span>;
  }

  const original = summary.originalBytes;
  const optimised = summary.optimisedBytes;
  if (!original) {
    return <span className="text-ink-faint">—</span>;
  }
  if (optimised > original) {
    return (
      <span className="text-ink-faint" title="Los derivados pesan más que el original">
        mayor
      </span>
    );
  }
  if (optimised === original) {
    return (
      <span className="text-ink-faint" title="El derivado pesa lo mismo que el original">
        sin cambio
      </span>
    );
  }

  return (
    <span className="tnum text-forest">
      {formatPercent(((original - optimised) / original) * 100)}
    </span>
  );
}

export function EvidenceTable({
  evidence,
  summaries,
  onInspect,
}: {
  evidence: Evidence[];
  summaries: Record<string, DetailSummary>;
  onInspect: (id: string) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-card border border-rule bg-surface">
      {/*
        No "Expediente" column: this view is already scoped to one file, so the
        case number on every row is noise — and it is wide enough to push the
        custody action out of reach. The number is shown once, in the heading.
      */}
      <table className="ledger min-w-[54rem]">
        <caption className="sr-only">
          Evidencias del expediente: tipo, fecha, peso original, peso optimizado,
          reducción, estado, integridad y visibilidad
        </caption>
        <thead>
          <tr className="label-rule [&_th]:whitespace-nowrap [&_th]:pr-4">
            <th scope="col">Evidencia</th>
            <th scope="col">Tipo</th>
            <th scope="col">Fecha</th>
            <th scope="col" className="text-right">Original</th>
            <th scope="col" className="text-right">Optimizado</th>
            <th scope="col" className="text-right">Reducción</th>
            <th scope="col">Estado</th>
            <th scope="col">Integridad</th>
            <th scope="col">Visibilidad</th>
            <th scope="col" className="text-right">
              <span className="sr-only">Acciones</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {evidence.map((item) => {
            const tone = evidenceStatusTone(item.status);
            const summary = summaries[item.id];
            const original = summary?.originalBytes ?? item.original_size ?? null;
            const hasDerivatives = (summary?.derivativeCount ?? item.derivative_count) > 0;
            const optimised = summary && hasDerivatives ? summary.optimisedBytes : null;
            return (
              <tr key={item.id}>
                <td className="py-3 pr-4">
                  <span className="block max-w-[17rem] truncate font-medium text-ink">
                    {item.title}
                  </span>
                  <span className="block max-w-[17rem] truncate text-xs text-ink-faint">
                    {item.original_filename ?? "sin archivo"}
                  </span>
                </td>
                <td className="py-3 pr-4 text-xs whitespace-nowrap text-ink-soft">
                  {evidenceTypeLabel(item.evidence_type)}
                  {item.is_signed_pdf ? (
                    <span className="mt-0.5 block text-[0.625rem] text-brass">
                      firmado
                    </span>
                  ) : null}
                </td>
                <td className="py-3 pr-4 text-xs whitespace-nowrap text-ink-soft">
                  {formatDate(item.captured_at ?? item.created_at)}
                </td>
                <td className="tnum py-3 pr-4 text-right text-xs whitespace-nowrap text-ink">
                  {formatBytes(original)}
                </td>
                <td className="tnum py-3 pr-4 text-right text-xs whitespace-nowrap text-ink">
                  {optimised === null ? (
                    <span className="text-ink-faint" title="Sin derivados">
                      —
                    </span>
                  ) : (
                    formatBytes(optimised)
                  )}
                </td>
                <td className="py-3 pr-4 text-right text-xs whitespace-nowrap">
                  {reductionView(item, summary)}
                </td>
                <td className="py-3 pr-4">
                  <Chip tone={tone}>{evidenceStatusLabel(item.status)}</Chip>
                </td>
                <td className="py-3 pr-4">
                  <HashChip
                    value={item.original_sha256}
                    tone={item.original_sha256 ? "forest" : "neutral"}
                  />
                </td>
                <td className="py-3 pr-4">
                  <Chip tone={visibilityTone(item.visibility)}>
                    {visibilityLabel(item.visibility)}
                  </Chip>
                </td>
                {/* The right padding matters: without it the action sits flush
                    against the border and reads as clipped even though the
                    table does not overflow. */}
                <td className="py-3 pr-4 text-right">
                  <button
                    type="button"
                    onClick={() => onInspect(item.id)}
                    className="text-xs font-semibold whitespace-nowrap text-wax underline-offset-4 transition-colors hover:underline"
                  >
                    Custodia
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
