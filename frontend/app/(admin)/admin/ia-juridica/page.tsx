import Link from "next/link";
import { redirect } from "next/navigation";

import { Button } from "@/components/admin/form-controls";
import { IaGenerate } from "@/components/admin/ia-generate";
import { PageHeader } from "@/components/admin/page-furniture";
import { Card, Chip, EmptyState, RuleNote } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { ApiNotAuthenticated, apiFetch } from "@/lib/api";
import type { Tone } from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type {
  LegalHitKind,
  LegalProviderStatus,
  LegalSearchHit,
  LegalSearchResponse,
  LegalSummary,
} from "@/lib/types";

/**
 * IA Jurídica (MASTER_PROMPT V5), the part of it that can be true today.
 *
 * Three things are real: a **lexical search** over cases, documents and the
 * multimedia library; an **extractive summary** that quotes a document's own
 * sentences; and a **draft generator** that only answers when the environment
 * carries `AI_PROVIDER` and `AI_API_KEY` — without them the panel names what is
 * missing and the box stays inert. Every draft comes back marked
 * `requires_review`, because it is raw material for a lawyer, never a finished
 * text.
 *
 * There are no embeddings, no vector store and no queue: search stays lexical so
 * a hit can be explained, and the generator has no memory of what it produced
 * until a lawyer saves it. Sending client data to an external provider is the
 * firm's professional-secrecy decision, not a setting on this screen.
 */

const MIN_QUERY = 2;
const MAX_HITS = 20;

export default async function LegalAiPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} backHref="/admin" />;
  }

  const { profile } = session;
  const can = (permission: string) => profile.permissions.includes(permission);
  const canSearch = can("ai:search");
  const canSummarise = can("ai:summarize");

  if (!canSearch) {
    return (
      <div>
        <PageHeader
          eyebrow="Asistencia"
          title="IA Jurídica"
          description="Su perfil no tiene el permiso para consultar el índice del estudio."
        />
        <div className="mt-6">
          <EmptyState
            title="Sin acceso a esta sección"
            hint="La búsqueda recorre expedientes, documentos y la biblioteca de toda la firma; consulte con un administrador si la necesita."
          />
        </div>
      </div>
    );
  }

  const params = await searchParams;
  const query = (first(params.q) ?? "").trim();
  const summaryFor = first(params.doc);

  const { value: provider } = await load<LegalProviderStatus>("/api/v1/ai/provider");

  // A query that is only stop words, or one character long, is answered by the API
  // with an error or an empty result. Neither is worth a failed request, and both
  // would look like a broken screen, so the screen asks first.
  const searched = query.length >= MIN_QUERY;
  const { value: results, failed } = searched
    ? await load<LegalSearchResponse>("/api/v1/ai/search", { q: query, limit: MAX_HITS })
    : { value: null, failed: false };

  const { value: summary, failed: summaryFailed } =
    canSummarise && summaryFor
      ? await load<LegalSummary>(`/api/v1/ai/documents/${summaryFor}/summary`)
      : { value: null, failed: false };

  const hits = results?.items ?? [];
  const hrefWith = (next: { q?: string; doc?: string }) => {
    const search = new URLSearchParams();
    const q = next.q ?? query;
    if (q) search.set("q", q);
    const doc = next.doc ?? "";
    if (doc) search.set("doc", doc);
    return `/admin/ia-juridica${search.size > 0 ? `?${search.toString()}` : ""}`;
  };

  return (
    <div>
      <PageHeader
        eyebrow="Asistencia"
        title="IA Jurídica"
        description="Busque en expedientes, documentos y la biblioteca a la vez, y lea un resumen hecho de las frases del propio documento. Lo que aparece aquí es lo que el sistema puede sostener: una búsqueda literal y un resumen extractivo."
      />

      <form method="get" action="/admin/ia-juridica" className="mt-6 flex flex-wrap items-end gap-3">
        <div className="min-w-[16rem] flex-1">
          <label htmlFor="q" className="label-rule block">
            Buscar en el estudio
          </label>
          <input
            id="q"
            name="q"
            type="search"
            defaultValue={query}
            minLength={MIN_QUERY}
            required
            placeholder="arrendamiento, indemnización, nulidad…"
            className="mt-1.5 w-full rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax"
          />
        </div>
        <Button type="submit">Buscar</Button>
        {query ? (
          <Link
            href="/admin/ia-juridica"
            className="pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted underline-offset-4 hover:text-wax hover:underline"
          >
            Limpiar
          </Link>
        ) : null}
      </form>

      <ProviderPanel status={provider} />

      <div className="mt-6">
        <IaGenerate />
      </div>

      {summary || summaryFailed || summaryFor ? (
        <div className="mt-6">
          <SummaryPanel summary={summary} failed={summaryFailed} closeHref={hrefWith({ doc: "" })} />
        </div>
      ) : null}

      {searched && failed ? (
        <p className="mt-6 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
          No fue posible consultar el índice. Una búsqueda sin resultados y una búsqueda
          que no se pudo ejecutar no son lo mismo, y esta pantalla no las confunde.
        </p>
      ) : null}

      {searched && results ? (
        <div className="mt-6">
          <p className="text-sm text-ink-muted">
            {results.total === 0 ? (
              <>Ningún resultado para «{results.query}».</>
            ) : (
              <>
                {results.total} resultado{results.total === 1 ? "" : "s"} para «
                {results.query}»
              </>
            )}
          </p>

          {results.terms.length > 0 ? (
            <p className="mt-1 text-xs text-ink-faint">
              Se buscó por:{" "}
              {results.terms.map((term) => (
                <span key={term} className="mr-1.5 font-mono text-ink-muted">
                  {term}
                </span>
              ))}
              {results.terms.length < results.query.split(/\s+/).filter(Boolean).length
                ? " — las palabras vacías se descartaron."
                : ""}
            </p>
          ) : (
            <p className="mt-1 text-xs text-brass">
              La consulta sólo contiene palabras vacías. Con una de esas palabras
              «coincidiría» con todo el estudio, así que no se buscó nada.
            </p>
          )}

          {hits.length > 0 ? (
            <ul className="mt-4 space-y-3">
              {hits.map((hit) => (
                <li key={`${hit.kind}-${hit.id}`}>
                  <HitCard
                    hit={hit}
                    canSummarise={canSummarise}
                    summaryHref={hrefWith({ doc: hit.kind === "document" ? hit.id : "" })}
                    caseHref={hit.case_id ? `/admin/expedientes/${hit.case_id}` : undefined}
                  />
                </li>
              ))}
            </ul>
          ) : null}

          {results.total > hits.length ? (
            <p className="mt-4 text-xs text-ink-faint">
              Se muestran {hits.length} de {results.total}. Acote la búsqueda con más
              palabras para reducir el resultado.
            </p>
          ) : null}
        </div>
      ) : null}

      {!searched && query ? (
        <p className="mt-6 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
          La búsqueda necesita al menos {MIN_QUERY} caracteres.
        </p>
      ) : null}

      {!query ? (
        <div className="mt-6">
          <EmptyState
            title="Nada buscado todavía"
            hint="Escriba una palabra o dos. La búsqueda recorre expedientes, documentos y la biblioteca, y sólo devuelve material que su perfil ya puede abrir."
          />
        </div>
      ) : null}

      <RuleNote>
        La búsqueda es literal: encuentra la palabra escrita, no su significado, y por
        eso muestra arriba las palabras con las que efectivamente buscó. El resumen
        copia frases del documento y no las reescribe —por eso se indica que es
        extractivo—, porque un resumen que reescribe es una afirmación, y una
        afirmación sobre un expediente tiene que poder rastrearse hasta la frase que
        la sostiene. Los resúmenes no leen el contenido de un PDF: si el texto está
        dentro del archivo, este resumen se lo dirá en lugar de inventarse uno.
      </RuleNote>
    </div>
  );
}

function HitCard({
  hit,
  canSummarise,
  summaryHref,
  caseHref,
}: {
  hit: LegalSearchHit;
  canSummarise: boolean;
  summaryHref: string;
  caseHref?: string;
}) {
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Chip tone={KIND_TONE[hit.kind]}>{KIND_LABEL[hit.kind]}</Chip>
            {hit.case_number ? (
              <span className="text-xs text-ink-faint">{hit.case_number}</span>
            ) : (
              <span className="text-xs text-ink-faint">Material de la firma</span>
            )}
          </div>
          <p className="mt-2 font-medium text-ink">{hit.title}</p>
          {hit.excerpt ? (
            <p className="mt-1 max-w-[46rem] text-sm leading-relaxed text-ink-muted">
              {hit.excerpt}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <span className="tnum text-xs text-ink-faint" title="Puntuación de relevancia">
            {hit.score.toFixed(2)}
          </span>
          <div className="flex flex-wrap justify-end gap-2">
            {caseHref ? (
              <Link href={caseHref} className="text-xs font-semibold text-wax hover:underline">
                Ver expediente
              </Link>
            ) : null}
            {hit.kind === "document" && canSummarise ? (
              <Link href={summaryHref} className="text-xs font-semibold text-wax hover:underline">
                Resumir
              </Link>
            ) : null}
          </div>
        </div>
      </div>
    </Card>
  );
}

function SummaryPanel({
  summary,
  failed,
  closeHref,
}: {
  summary: LegalSummary | null;
  failed: boolean;
  closeHref: string;
}) {
  return (
    <Card className="border-wax/40">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="label-rule">Resumen</p>
          <p className="mt-1 font-medium text-ink">{summary?.title ?? "Documento"}</p>
        </div>
        <div className="flex items-center gap-2">
          {summary ? <Chip tone="forest">Extractivo</Chip> : null}
          <Link href={closeHref} className="text-xs font-semibold text-wax hover:underline">
            Cerrar
          </Link>
        </div>
      </div>

      {failed ? (
        <p className="mt-3 text-sm text-brass">
          No fue posible resumir este documento. Puede que no exista, que esté fuera
          de los expedientes de su perfil, o que no tenga texto disponible.
        </p>
      ) : null}

      {summary ? (
        <>
          <ol className="mt-4 space-y-2 border-l-2 border-rule pl-4">
            {summary.sentences.map((sentence, index) => (
              <li key={`${index}-${sentence.slice(0, 24)}`} className="text-sm leading-relaxed text-ink">
                {sentence}
              </li>
            ))}
          </ol>
          <p className="mt-3 text-xs text-ink-faint">
            {summary.sentences.length} frase{summary.sentences.length === 1 ? "" : "s"} del
            propio documento, sin reescribir. Pesó sobre:{" "}
            {summary.terms.length > 0 ? summary.terms.join(", ") : "—"}
          </p>
        </>
      ) : null}

      {!summary && !failed ? (
        <p className="mt-3 text-sm text-ink-muted">No hay resumen que mostrar.</p>
      ) : null}
    </Card>
  );
}

/**
 * Say what is missing, by name.
 *
 * The alternative — a disabled text box with "próximamente" — costs the reader the
 * one thing they need: what to arrange. Naming the four absences turns an empty
 * screen into a shopping list, and it is the same list the API reports, so the two
 * cannot drift apart.
 */
function ProviderPanel({ status }: { status: LegalProviderStatus | null }) {
  if (!status) return null;

  const pieces: { label: string; ready: boolean }[] = [
    { label: "Proveedor de lenguaje", ready: Boolean(status.provider) },
    { label: "Modelo", ready: Boolean(status.model) },
    { label: "Embeddings", ready: status.embeddings },
    { label: "Almacén vectorial", ready: status.vector_store },
    { label: "Cola de trabajo", ready: status.queue },
  ];

  return (
    <Card className="mt-6">
      <p className="label-rule">Generación asistida</p>
      {status.available ? (
        <p className="mt-2 text-sm text-ink-muted">
          Hay un proveedor configurado. Los resúmenes de esta pantalla siguen siendo
          extractivos: la generación no está conectada al índice.
        </p>
      ) : (
        <p className="mt-2 text-sm text-ink-muted">
          Este módulo no llama a ningún modelo. La búsqueda y el resumen que ve son
          lexicales y extractivos, respectivamente; no hay conversación con un
          asistente ni generación de texto. Para habilitarla falta:
        </p>
      )}
      <ul className="mt-3 grid gap-1.5 sm:grid-cols-2">
        {pieces.map((piece) => (
          <li key={piece.label} className="flex items-center gap-2 text-sm">
            <Chip tone={piece.ready ? "forest" : "brass"}>
              {piece.ready ? "Listo" : "Falta"}
            </Chip>
            <span className={piece.ready ? "text-ink-muted" : "text-ink"}>{piece.label}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

const KIND_LABEL: Record<LegalHitKind, string> = {
  case: "Expediente",
  document: "Documento",
  media: "Biblioteca",
};

const KIND_TONE: Record<LegalHitKind, Tone> = {
  case: "wax",
  document: "forest",
  media: "brass",
};

/**
 * Load for a signed-in caller.
 *
 * Redirects only when the session is genuinely gone; anything else returns null
 * with `failed`, because "no results" and "could not ask" must not look alike.
 */
async function load<T>(
  path: string,
  query: Record<string, string | number | boolean | undefined> = {},
): Promise<{ value: T | null; failed: boolean }> {
  try {
    return { value: await apiFetch<T>(path, { query }), failed: false };
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) redirect("/login");
    return { value: null, failed: true };
  }
}

function first(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}
