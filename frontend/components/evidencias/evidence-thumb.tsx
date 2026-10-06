"use client";

import { useEffect, useState } from "react";

import { fileExtensionOf } from "@/lib/format";

/**
 * A thumbnail that fetches the evidence only when it scrolls into view.
 *
 * The list endpoint returns counts, not derivative identifiers, so a thumbnail
 * needs the detail. Fetching all of them on load would turn a list of a hundred
 * evidences into a hundred requests; the intersection observer means only the
 * visible cards ask.
 */
export function EvidenceThumb({
  evidenceId,
  fileName,
  mimeType,
}: {
  evidenceId: string;
  fileName: string | null;
  mimeType: string | null;
}) {
  const [source, setSource] = useState<string | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "none">("idle");
  const [host, setHost] = useState<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!host || state !== "idle") return;
    if (typeof IntersectionObserver === "undefined") {
      void load(evidenceId, setSource, setState);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        observer.disconnect();
        void load(evidenceId, setSource, setState);
      },
      { rootMargin: "200px" },
    );
    observer.observe(host);
    return () => observer.disconnect();
  }, [evidenceId, host, state]);

  const extension = fileExtensionOf(fileName);
  const isImage = mimeType?.startsWith("image/") ?? false;

  return (
    <div
      ref={setHost}
      className="relative grid aspect-[4/3] w-full place-items-center overflow-hidden rounded-t-card bg-paper-deep"
    >
      {source ? (
        // The derivative is served by our own route, which streams it with the
        // credential attached server side.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={source}
          alt={`Vista previa de ${fileName ?? "la evidencia"}`}
          className="size-full object-cover"
          loading="lazy"
        />
      ) : mimeType ? (
        isImage ? (
          <span
            aria-hidden="true"
            className={`text-[0.6875rem] font-semibold uppercase tracking-[0.2em] ${
              state === "loading" ? "text-ink-faint/50" : "text-ink-faint"
            }`}
          >
            {state === "loading" ? "Generando" : "Sin vista previa"}
          </span>
        ) : (
          <span
            aria-hidden="true"
            className="font-display text-2xl tracking-wide text-ink-faint"
          >
            {(extension || "?").toUpperCase()}
          </span>
        )
      ) : (
        /*
          No MIME at all means no original was ever stored, which is what a
          quarantined file looks like. A question mark would read as "we could
          not read this"; the truth is "there is nothing here yet".
        */
        <span aria-hidden="true" className="stamp text-[0.6875rem] font-semibold uppercase tracking-[0.2em] text-wax/70">
          Sin original
        </span>
      )}

      {mimeType && !isImage ? (
        <span className="absolute right-2 bottom-2 rounded-sm bg-ink/80 px-1.5 py-0.5 text-[0.625rem] font-semibold tracking-wider text-paper">
          {extension.toUpperCase()}
        </span>
      ) : null}
    </div>
  );
}

async function load(
  evidenceId: string,
  setSource: (value: string) => void,
  setState: (value: "loading" | "none") => void,
): Promise<void> {
  setState("loading");
  try {
    const response = await fetch(`/api/proxy/evidences/${evidenceId}`, {
      cache: "no-store",
    });
    if (!response.ok) {
      setState("none");
      return;
    }
    const detail = (await response.json()) as {
      derivatives?: Array<{ id: string; derivative_type: string; mime_type: string }>;
    };
    // A preview first; any image derivative is a better thumbnail than none.
    const candidates = (detail.derivatives ?? []).filter(
      (item) => item.mime_type?.startsWith("image/"),
    );
    const chosen =
      candidates.find((item) => item.derivative_type === "preview") ?? candidates[0];

    if (!chosen) {
      setState("none");
      return;
    }
    setSource(`/api/descarga/evidences/${evidenceId}/derivatives/${chosen.id}`);
  } catch {
    setState("none");
  }
}
