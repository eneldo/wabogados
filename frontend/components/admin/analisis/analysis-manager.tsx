"use client";

import { useState } from "react";

type Analysis = {
  id: string;
  title: string;
  slug: string;
  summary: string | null;
  content: string;
  author_name: string | null;
  is_published: boolean;
  published_at: string | null;
  is_active: boolean;
};

export function AnalysisManager({ initial }: { initial: Analysis[] }) {
  const [items, setItems] = useState<Analysis[]>(initial);
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const res = await fetch("/api/proxy/api/v1/analyses");
    if (res.ok) setItems(await res.json());
  }

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/proxy/api/v1/analyses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, slug, content, is_published: false }),
      });
      if (!res.ok) throw new Error(await res.text());
      setTitle("");
      setSlug("");
      setContent("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setBusy(true);
    try {
      await fetch(`/api/proxy/api/v1/analyses/${id}`, { method: "DELETE" });
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function togglePublish(item: Analysis) {
    setBusy(true);
    try {
      await fetch(`/api/proxy/api/v1/analyses/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_published: !item.is_published }),
      });
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-card border border-rule bg-surface p-6">
        <h2 className="font-display text-xl">Nuevo análisis</h2>
        <div className="mt-4 grid gap-3">
          <input
            className="rounded-card border border-rule bg-canvas px-3 py-2 text-sm"
            placeholder="Título"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <input
            className="rounded-card border border-rule bg-canvas px-3 py-2 text-sm"
            placeholder="Slug (url)"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
          />
          <textarea
            className="rounded-card border border-rule bg-canvas px-3 py-2 text-sm"
            placeholder="Contenido"
            rows={6}
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
          {error ? <p className="text-sm text-wax">{error}</p> : null}
          <button
            onClick={create}
            disabled={busy}
            className="rounded-card bg-action px-4 py-2 text-sm font-semibold text-on-action disabled:opacity-50"
          >
            Crear
          </button>
        </div>
      </div>

      <div className="space-y-3">
        {items.map((item) => (
          <div
            key={item.id}
            className="rounded-card border border-rule bg-surface p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-display text-lg">{item.title}</h3>
                <p className="text-xs text-ink-muted">
                  {item.is_published ? "Publicado" : "Borrador"} · {item.slug}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => togglePublish(item)}
                  disabled={busy}
                  className="rounded-card border border-rule-strong px-3 py-1.5 text-xs"
                >
                  {item.is_published ? "Despublicar" : "Publicar"}
                </button>
                <button
                  onClick={() => remove(item.id)}
                  disabled={busy}
                  className="rounded-card border border-danger-strong px-3 py-1.5 text-xs text-wax"
                >
                  Desactivar
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}