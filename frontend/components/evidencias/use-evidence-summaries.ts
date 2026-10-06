"use client";

import { useEffect, useRef, useState } from "react";

import type { EvidenceDetail } from "@/lib/types";

export type DetailSummary = {
  originalBytes: number | null;
  optimisedBytes: number;
  hasPreview: boolean;
  derivativeCount: number;
  pages: number | null;
  signed: boolean;
  signatureBroken: boolean;
};

const EMPTY: DetailSummary = {
  originalBytes: null,
  optimisedBytes: 0,
  hasPreview: false,
  derivativeCount: 0,
  pages: null,
  signed: false,
  signatureBroken: false,
};

/**
 * Derivative weights for the table.
 *
 * The list endpoint reports how many derivatives an evidence has, not what they
 * weigh, so "peso optimizado" and "reducción" — two of the columns section 39
 * asks for — cannot be computed from it. Rather than render a column of dashes
 * or guess, the details are fetched once per evidence and cached for the
 * session.
 *
 * Results are keyed by evidence id, so a second render never refetches, and the
 * caller can show a placeholder for rows that have not arrived yet.
 */
export function useEvidenceSummaries(
  ids: string[],
  enabled: boolean,
): Record<string, DetailSummary> {
  const [summaries, setSummaries] = useState<Record<string, DetailSummary>>({});
  const requested = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!enabled) return;
    const missing = ids.filter((id) => !requested.current.has(id));
    if (missing.length === 0) return;
    missing.forEach((id) => requested.current.add(id));

    let cancelled = false;

    void (async () => {
      // Sequentially, not all at once: a hundred-row table would otherwise open
      // a hundred sockets against the API and be refused.
      for (const id of missing) {
        try {
          const response = await fetch(`/api/proxy/evidences/${id}`, {
            cache: "no-store",
          });
          if (!response.ok) continue;
          const detail = (await response.json()) as EvidenceDetail;
          if (cancelled) return;

          const original =
            detail.files.find((item) => item.is_original) ?? detail.files[0];
          const derivatives = detail.derivatives ?? [];

          setSummaries((current) => ({
            ...current,
            [id]: {
              originalBytes: original?.file_size ?? detail.original_size ?? null,
              optimisedBytes: derivatives.reduce(
                (total, item) => total + (item.size_bytes ?? 0),
                0,
              ),
              hasPreview: derivatives.some(
                (item) => item.derivative_type === "preview",
              ),
              derivativeCount: derivatives.length,
              pages: detail.files[0]?.page_count ?? null,
              signed: detail.is_signed_pdf,
              signatureBroken: detail.files.some((item) => item.signature_broken),
            },
          }));
        } catch {
          // A failed detail fetch leaves the row without figures, which the
          // table renders as a placeholder rather than a wrong number.
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [enabled, ids]);

  return summaries;
}

export { EMPTY as EMPTY_SUMMARY };
