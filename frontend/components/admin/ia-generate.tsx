"use client";

import { useState } from "react";

export function IaGenerate() {
  const [prompt, setPrompt] = useState("");
  const [context, setContext] = useState("");
  const [draft, setDraft] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setError(null);
    setDraft(null);
    try {
      const res = await fetch("/api/proxy/api/v1/ai/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, context }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Error");
      setDraft(data.draft);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-card border border-rule bg-surface p-6">
      <h2 className="font-display text-xl">Generación asistida (borrador)</h2>
      <p className="mt-2 text-sm text-ink-muted">
        Requiere proveedor configurado. El resultado debe ser revisado por un abogado.
      </p>
      <div className="mt-4 grid gap-3">
        <textarea
          className="rounded-card border border-rule bg-canvas px-3 py-2 text-sm"
          placeholder="Solicitud (ej. redactar borrador de contestación)"
          rows={3}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <textarea
          className="rounded-card border border-rule bg-canvas px-3 py-2 text-sm"
          placeholder="Contexto (expediente, hechos, normas)"
          rows={5}
          value={context}
          onChange={(e) => setContext(e.target.value)}
        />
        {error ? <p className="text-sm text-wax">{error}</p> : null}
        <button
          onClick={run}
          disabled={busy || !prompt.trim()}
          className="rounded-card bg-action px-4 py-2 text-sm font-semibold text-on-action disabled:opacity-50"
        >
          Generar borrador
        </button>
        {draft ? (
          <pre className="mt-4 whitespace-pre-wrap rounded-card border border-rule bg-canvas p-4 text-sm">
            {draft}
          </pre>
        ) : null}
      </div>
    </div>
  );
}