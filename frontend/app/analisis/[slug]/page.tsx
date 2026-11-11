import Link from "next/link";

import { apiFetchOr } from "@/lib/api";

export default async function AnalysisDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const analysis = await apiFetchOr<{
    title: string;
    slug: string;
    summary: string | null;
    content: string;
    author_name: string | null;
    published_at: string | null;
  } | null>(null, `/api/v1/public/analyses/${slug}`, { anonymous: true });

  if (!analysis) {
    return (
      <main className="grid min-h-screen place-items-center px-6">
        <div className="rounded-card border border-rule bg-surface p-8 text-center">
          <h1 className="font-display text-2xl">Análisis no encontrado</h1>
          <Link href="/" className="mt-4 inline-block text-wax underline">
            Volver al inicio
          </Link>
        </div>
      </main>
    );
  }

  return (
    <div className="public-site">
      <main className="wrap py-16">
        <Link href="/" className="text-sm text-wax underline-offset-4 hover:underline">
          ← Volver al inicio
        </Link>
        <h1 className="site-display mt-6 text-3xl sm:text-4xl">{analysis.title}</h1>
        <div className="mt-2 flex gap-4 text-xs text-ink-muted">
          <span>{analysis.author_name ?? "Despacho"}</span>
          {analysis.published_at ? (
            <span>{new Date(analysis.published_at).toLocaleDateString("es-CO")}</span>
          ) : null}
        </div>
        {analysis.summary ? (
          <p className="site-body mt-6 max-w-[60ch]">{analysis.summary}</p>
        ) : null}
        <article className="mt-8 max-w-[70ch] whitespace-pre-wrap text-ink-soft">
          {analysis.content}
        </article>
      </main>
    </div>
  );
}