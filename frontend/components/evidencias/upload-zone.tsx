"use client";

import { useCallback, useRef, useState } from "react";

import { StageRail } from "./stage-rail";
import {
  ACCEPTED_LABEL,
  isAccepted,
  type Stage,
} from "./stages";
import type { EvidenceUploadResult } from "@/lib/types";

/**
 * Drop zone and upload.
 *
 * Progress comes from `XMLHttpRequest.upload.onprogress`, which reports real
 * bytes on the wire. The later stages are driven by the server's answer and by
 * polling while it works; see `stages.ts` for why the middle of the pipeline
 * cannot be observed separately.
 *
 * Nothing is sent to the API directly. The request goes to this app's proxy,
 * which attaches the credential server side, so the bearer token never reaches
 * the browser.
 */

type Job = {
  id: string;
  fileName: string;
  fileSize: number;
  stage: Stage;
  percent: number;
  message: string | null;
  evidenceId: string | null;
};

type NewEvidence = {
  title: string;
  evidence_type: string;
  visibility: string;
  confidentiality: string;
};

const EVIDENCE_TYPES = [
  { value: "documental", label: "Documental" },
  { value: "fotografica", label: "Fotográfica" },
  { value: "testifical", label: "Testifical" },
  { value: "pericial", label: "Pericial" },
  { value: "informatica", label: "Informática" },
  { value: "audio", label: "Audio" },
  { value: "video", label: "Vídeo" },
];

let jobCounter = 0;

function humanTitle(fileName: string): string {
  return fileName
    .replace(/\.[^.]+$/, "")
    .replace(/[_-]+/g, " ")
    .trim()
    .slice(0, 120);
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`/api/proxy${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      (payload as { error?: { message?: string } } | null)?.error?.message ??
      "No fue posible completar la operación.";
    throw new Error(message);
  }
  return payload as T;
}

export function UploadZone({
  caseId,
  onUploaded,
}: {
  caseId: string;
  onUploaded: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [meta, setMeta] = useState<NewEvidence>({
    title: "",
    evidence_type: "documental",
    visibility: "interna",
    confidentiality: "interno",
  });

  const patch = useCallback((id: string, changes: Partial<Job>) => {
    setJobs((current) =>
      current.map((job) => (job.id === id ? { ...job, ...changes } : job)),
    );
  }, []);

  /**
   * Wait for the worker to finish deriving, when the server queued the work.
   * Bounded: an evidence that never leaves `processing` stops being polled and
   * says so, rather than spinning forever.
   */
  const followQueuedWork = useCallback(
    async (jobId: string, evidenceId: string) => {
      for (let attempt = 0; attempt < 30; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        try {
          const response = await fetch(`/api/proxy/evidences/${evidenceId}`, {
            cache: "no-store",
          });
          if (!response.ok) return;
          const evidence = (await response.json()) as {
            status: string;
            derivatives?: Array<{ derivative_type: string }>;
          };
          const derivatives = evidence.derivatives ?? [];
          const hasPreview = derivatives.some(
            (item) => item.derivative_type === "preview",
          );

          if (evidence.status === "quarantined" || evidence.status === "failed") {
            patch(jobId, { stage: "rechazado", message: null });
            return;
          }
          if (evidence.status === "ready" || evidence.status === "archived") {
            patch(jobId, { stage: "listo", percent: 100, message: null });
            onUploaded();
            return;
          }
          patch(jobId, {
            stage: hasPreview || derivatives.length > 0 ? "optimizando" : "seguridad",
          });
        } catch {
          return;
        }
      }
      patch(jobId, {
        stage: "optimizando",
        message:
          "El procesado continúa en segundo plano. La evidencia aparecerá como «Procesando» y se actualizará sola.",
      });
    },
    [onUploaded, patch],
  );

  const upload = useCallback(
    async (file: File, jobId: string) => {
      try {
        patch(jobId, { stage: "validando", percent: 100 });

        const created = await postJson<{ id: string }>(
          `/cases/${caseId}/evidences`,
          {
            case_id: caseId,
            title: meta.title.trim() || humanTitle(file.name),
            evidence_type: meta.evidence_type,
            visibility: meta.visibility,
            confidentiality: meta.confidentiality,
          },
        );
        patch(jobId, { evidenceId: created.id, stage: "seguridad" });

        // XHR rather than fetch: fetch still cannot report upload progress.
        const result = await new Promise<EvidenceUploadResult>((resolve, reject) => {
          const request = new XMLHttpRequest();
          const form = new FormData();
          form.append("file", file, file.name);

          request.open("POST", `/api/proxy/evidences/${created.id}/original`);
          request.upload.onprogress = (event) => {
            if (!event.lengthComputable) return;
            const ratio = Math.round((event.loaded / event.total) * 100);
            patch(jobId, {
              stage: ratio >= 100 ? "validando" : "subiendo",
              percent: ratio,
            });
          };
          request.onload = () => {
            let payload: EvidenceUploadResult | null = null;
            try {
              payload = JSON.parse(request.responseText) as EvidenceUploadResult;
            } catch {
              payload = null;
            }
            if (request.status >= 200 && request.status < 300 && payload) {
              resolve(payload);
            } else {
              const message =
                (payload as unknown as { error?: { message?: string } } | null)?.error
                  ?.message ?? "El despacho rechazó el archivo.";
              reject(new Error(message));
            }
          };
          request.onerror = () => reject(new Error("Se perdió la conexión."));
          request.send(form);
        });

        patch(jobId, { stage: "seguridad", percent: 100 });
        onUploaded();

        if (result.queued) {
          patch(jobId, { stage: "optimizando" });
          void followQueuedWork(jobId, result.evidence.id);
        } else {
          const hasPreview = result.evidence.derivatives.some(
            (item) => item.derivative_type === "preview",
          );
          patch(jobId, {
            stage: hasPreview ? "optimizando" : "vista_previa",
          });
          // The synchronous path is done, but the last station should still be
          // reached rather than jumping from four to six.
          window.setTimeout(() => {
            patch(jobId, { stage: "vista_previa" });
            window.setTimeout(
              () => patch(jobId, { stage: "listo", message: result.detail }),
              700,
            );
          }, 600);
        }
      } catch (error) {
        patch(jobId, {
          stage: "rechazado",
          message: error instanceof Error ? error.message : "Error inesperado.",
        });
      }
    },
    [caseId, followQueuedWork, meta, onUploaded, patch],
  );

  const accept = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      for (const file of Array.from(files)) {
        jobCounter += 1;
        const jobId = `job-${jobCounter}`;
        const rejected = !isAccepted(file);

        setJobs((current) => [
          ...current,
          {
            id: jobId,
            fileName: file.name,
            fileSize: file.size,
            stage: rejected ? "rechazado" : "subiendo",
            percent: 0,
            message: rejected
              ? `Formato no admitido. Se aceptan ${ACCEPTED_LABEL}.`
              : null,
            evidenceId: null,
          },
        ]);

        if (!rejected) void upload(file, jobId);
      }
      setMeta((current) => ({ ...current, title: "" }));
    },
    [upload],
  );

  return (
    <div className="rounded-card border border-rule bg-surface">
      <div className="grid gap-5 p-5 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2">
          <label htmlFor="evidence-title" className="label-rule block">
            Título
          </label>
          <input
            id="evidence-title"
            value={meta.title}
            onChange={(event) => setMeta({ ...meta, title: event.target.value })}
            placeholder="Si se deja vacío se usa el nombre del archivo"
            className="mt-1.5 w-full rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-wax"
          />
        </div>

        <div>
          <label htmlFor="evidence-type" className="label-rule block">
            Tipo
          </label>
          <select
            id="evidence-type"
            value={meta.evidence_type}
            onChange={(event) => setMeta({ ...meta, evidence_type: event.target.value })}
            className="mt-1.5 w-full rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors focus:border-wax"
          >
            {EVIDENCE_TYPES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="evidence-visibility" className="label-rule block">
            Visibilidad
          </label>
          <select
            id="evidence-visibility"
            value={meta.visibility}
            onChange={(event) => setMeta({ ...meta, visibility: event.target.value })}
            className="mt-1.5 w-full rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors focus:border-wax"
          >
            <option value="interna">Interna</option>
            <option value="equipo">Equipo</option>
            <option value="publicada">Publicada al cliente</option>
          </select>
        </div>
      </div>

      <div
        className="dropzone relative mx-5 mb-5 cursor-pointer rounded-card border-2 border-dashed border-rule-strong bg-surface-sunk px-6 py-10 text-center transition-colors hover:border-wax/60"
        data-dragging={dragging}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          accept(event.dataTransfer.files);
        }}
        role="button"
        tabIndex={0}
        aria-label={`Arrastrar archivos aquí. Formatos aceptados: ${ACCEPTED_LABEL}`}
      >
        <p className="font-display text-xl text-ink">Arrastra archivos aquí</p>
        <p className="mt-1.5 text-sm text-ink-muted">{ACCEPTED_LABEL}</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff"
          onChange={(event) => accept(event.target.files)}
          className="sr-only"
        />
      </div>

      {jobs.length > 0 ? (
        <ul className="divide-y divide-rule border-t border-rule">
          {jobs.map((job) => (
            <li key={job.id} className="px-5 py-5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <p className="truncate text-sm font-medium text-ink">{job.fileName}</p>
                <p className="tnum text-xs text-ink-muted">
                  {formatJobSize(job.fileSize)}
                </p>
              </div>

              <div className="mt-4">
                <StageRail stage={job.stage} />
              </div>

              {job.stage === "subiendo" || job.stage === "validando" ? (
                <div
                  className="mt-4 h-1 w-full overflow-hidden rounded-full bg-paper-deep"
                  role="progressbar"
                  aria-valuenow={job.percent}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div
                    className="h-full rounded-full bg-forest transition-[width] duration-200"
                    style={{ width: `${job.percent}%` }}
                  />
                </div>
              ) : null}

              {job.message ? (
                <p
                  className={`mt-3 text-xs ${
                    job.stage === "rechazado" ? "text-wax-deep" : "text-ink-muted"
                  }`}
                >
                  {job.message}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function formatJobSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} kB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
