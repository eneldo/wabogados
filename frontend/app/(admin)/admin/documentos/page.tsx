import Link from "next/link";
import { redirect } from "next/navigation";

import { DocumentViewButton } from "@/components/admin/documentos/document-view";
import {
  FilterBar,
  FilterField,
  PageHeader,
  Pager,
} from "@/components/admin/page-furniture";
import { Button } from "@/components/admin/form-controls";
import { Card, Chip, EmptyState, RuleNote } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { ApiNotAuthenticated, apiFetch } from "@/lib/api";
import {
  confidentialityLabel,
  confidentialityTone,
  documentStatusLabel,
  documentStatusTone,
  documentTypeLabel,
  formatDateTime,
  visibilityLabel,
  visibilityTone,
} from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type { PaginatedDocuments } from "@/lib/types";

/**
 * The document browser.
 *
 * Documents are per-case everywhere else in the product; this is the one screen
 * that reads across cases, which is what a firm actually does when it asks
 * "where is the power of attorney for this signature". The query is the API's
 * `/documents`, whose scope filter is the same one the case listings use, so
 * this screen can only ever show what the caller could already reach.
 *
 * What is absent is deliberate: no "Eliminar". A document ends at `anulado`,
 * a version ends at being superseded, and both stay readable. Nothing here
 * overwrites an original either — a correction becomes a new version.
 */

const PAGE_SIZE = 25;

/**
 * What colour the row's left rule wears.
 *
 * An anulled or superseded document is history and stays a plain ledger line;
 * a document under legal hold is frozen by an order and wears brass, because
 * it is waiting on something outside the firm. Everything else is live.
 */
function rowAccent(record: { status: string; legal_hold: boolean }): string {
  if (record.status === "anulado" || record.status === "reemplazado") return "closed";
  if (record.legal_hold) return "held";
  return "live";
}

export default async function DocumentsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} backHref="/admin" />;
  }

  const permissions = session.profile.permissions;
  if (!permissions.includes("documents:read")) redirect("/admin");
  const canDownload = permissions.includes("documents:download");

  const params = await searchParams;
  const search = first(params.search);
  const documentType = first(params.document_type);
  const status = first(params.status);
  const confidentiality = first(params.confidentiality);
  const visibility = first(params.visibility);
  const legalHold = first(params.legal_hold) === "1";
  const skip = Math.max(0, Number(first(params.skip) ?? "0") || 0);

  const value = await fetchDocuments({
    search,
    documentType,
    status,
    confidentiality,
    visibility,
    legalHold,
    skip,
  });

  const documents = value?.items ?? [];
  const total = value?.total ?? 0;
  const failed = value === null;

  const hrefFor = (next: Record<string, string | number>) => {
    const query = new URLSearchParams();
    if (search) query.set("search", search);
    if (documentType) query.set("document_type", documentType);
    if (status) query.set("status", status);
    if (confidentiality) query.set("confidentiality", confidentiality);
    if (visibility) query.set("visibility", visibility);
    if (legalHold) query.set("legal_hold", "1");
    for (const [key, value] of Object.entries(next)) query.set(key, String(value));
    const text = query.toString();
    return text ? `/admin/documentos?${text}` : "/admin/documentos";
  };

  const filtered = Boolean(
    search || documentType || status || confidentiality || visibility || legalHold,
  );

  return (
    <div>
      <PageHeader
        eyebrow="Archivo"
        title="Documentos"
        description="El archivo de la firma, expediente por expediente. Un documento no se borra: se anula, y sus versiones anteriores siguen siendo legibles."
      />

      <FilterBar>
        <FilterField
          label="Buscar"
          name="search"
          defaultValue={search}
          placeholder="Título, descripción o expediente"
          className="min-w-[15rem] flex-1"
        />

        <div>
          <label htmlFor="filtro-document_type" className="label-rule block">
            Tipo
          </label>
          <select
            id="filtro-document_type"
            name="document_type"
            defaultValue={documentType ?? ""}
            className={SELECT}
          >
            <option value="">Todos</option>
            {DOCUMENT_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="filtro-status" className="label-rule block">
            Estado
          </label>
          <select
            id="filtro-status"
            name="status"
            defaultValue={status ?? ""}
            className={SELECT}
          >
            <option value="">Todos</option>
            <option value="borrador">Borrador</option>
            <option value="vigente">Vigente</option>
            <option value="reemplazado">Reemplazado</option>
            <option value="anulado">Anulado</option>
          </select>
        </div>

        <div>
          <label htmlFor="filtro-visibility" className="label-rule block">
            Visibilidad
          </label>
          <select
            id="filtro-visibility"
            name="visibility"
            defaultValue={visibility ?? ""}
            className={SELECT}
          >
            <option value="">Todas</option>
            <option value="interna">Interna</option>
            <option value="equipo">Equipo</option>
            <option value="publicada">Publicada</option>
          </select>
        </div>

        <div>
          <label htmlFor="filtro-confidentiality" className="label-rule block">
            Confidencialidad
          </label>
          <select
            id="filtro-confidentiality"
            name="confidentiality"
            defaultValue={confidentiality ?? ""}
            className={SELECT}
          >
            <option value="">Todas</option>
            <option value="publico">Público</option>
            <option value="interno">Interno</option>
            <option value="confidencial">Confidencial</option>
            <option value="secreto">Secreto</option>
          </select>
        </div>

        <label className="flex items-center gap-2 pb-2 text-sm text-ink-soft">
          <input
            type="checkbox"
            name="legal_hold"
            value="1"
            defaultChecked={legalHold}
            className="size-4 accent-wax"
          />
          Solo con retención congelada
        </label>

        <Button type="submit" variant="secondary">
          Filtrar
        </Button>
        {filtered ? (
          <Link
            href="/admin/documentos"
            className="pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted underline-offset-4 hover:text-wax hover:underline"
          >
            Limpiar
          </Link>
        ) : null}
      </FilterBar>

      {failed ? (
        <p className="mt-6 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
          No fue posible cargar el archivo. Un archivo vacío y un archivo que
          falló no son lo mismo, y este aviso es la diferencia.
        </p>
      ) : null}

      <div className="mt-6">
        {documents.length === 0 ? (
          <EmptyState
            title={filtered ? "No hay documentos que coincidan" : "No hay documentos"}
            hint={
              filtered
                ? "Pruebe con otro texto o quite los filtros."
                : "Los documentos se cargan desde cada expediente."
            }
          />
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="ledger min-w-[56rem]">
                <caption className="sr-only">
                  Listado de documentos, {total} en total
                </caption>
                <thead>
                  <tr>
                    <th scope="col" className="label-rule">
                      Documento
                    </th>
                    <th scope="col" className="label-rule">
                      Tipo
                    </th>
                    <th scope="col" className="label-rule">
                      Estado
                    </th>
                    <th scope="col" className="label-rule">
                      Visibilidad
                    </th>
                    <th scope="col" className="label-rule">
                      Confidencialidad
                    </th>
                    <th scope="col" className="label-rule">
                      Actualizado
                    </th>
                    <th scope="col" className="label-rule text-right">
                      <span className="sr-only">Acciones</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((record, index) => (
                    <tr
                      key={record.id}
                      data-accent={rowAccent(record)}
                      className="row-enter"
                      /* Only the first few rows are staggered; see globals.css. */
                      style={
                        index < 8 ? { animationDelay: `${index * 12}ms` } : undefined
                      }
                    >
                      <th scope="row" className="py-4 pr-4 font-normal">
                        <span className="row-title">{record.title}</span>
                        <span className="row-meta mt-1 block">
                          {record.case_number}
                          {record.version_count > 0
                            ? ` · ${record.version_count} ${record.version_count === 1 ? "versión" : "versiones"}`
                            : " · sin archivo"}
                        </span>
                      </th>
                      <td className="py-4 pr-4 text-[0.8125rem] text-ink-muted">
                        {documentTypeLabel(record.document_type)}
                      </td>
                      <td className="py-4 pr-4">
                        <Chip tone={documentStatusTone(record.status)}>
                          {documentStatusLabel(record.status)}
                        </Chip>
                        {record.legal_hold ? (
                          <span className="row-meta mt-1.5 block">Retención congelada</span>
                        ) : null}
                      </td>
                      <td className="py-4 pr-4">
                        <Chip tone={visibilityTone(record.visibility)}>
                          {visibilityLabel(record.visibility)}
                        </Chip>
                      </td>
                      <td className="py-4 pr-4">
                        <Chip tone={confidentialityTone(record.confidentiality)}>
                          {confidentialityLabel(record.confidentiality)}
                        </Chip>
                      </td>
                      <td className="tnum py-4 pr-4 text-[0.8125rem] text-ink-muted">
                        {formatDateTime(record.updated_at)}
                      </td>
                      <td className="py-4 text-right">
                        <div className="row-actions">
                          <DocumentViewButton
                            documentId={record.id}
                            canDownload={canDownload}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        <Pager
          total={total}
          skip={skip}
          limit={PAGE_SIZE}
          pageHref={(next) => hrefFor({ skip: next })}
        />

        <RuleNote>
          Un documento no se elimina: se anula y sigue consultable. Las versiones
          anteriores tampoco se borran ni se sobrescriben, porque el archivo que
          se firmó es el que debe poder reproducirse.
        </RuleNote>
      </div>
    </div>
  );
}

const SELECT =
  "mt-1.5 rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax";

const DOCUMENT_TYPE_OPTIONS = [
  { value: "contrato", label: "Contrato" },
  { value: "poder", label: "Poder" },
  { value: "demanda", label: "Demanda" },
  { value: "contestacion", label: "Contestación" },
  { value: "memorial", label: "Memorial" },
  { value: "auto", label: "Auto" },
  { value: "sentencia", label: "Sentencia" },
  { value: "prueba", label: "Prueba" },
  { value: "identificacion", label: "Identificación" },
  { value: "comunicacion", label: "Comunicación" },
  { value: "otro", label: "Otro" },
];

function first(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}

async function fetchDocuments(options: {
  search?: string;
  documentType?: string;
  status?: string;
  confidentiality?: string;
  visibility?: string;
  legalHold: boolean;
  skip: number;
}): Promise<PaginatedDocuments | null> {
  try {
    return await apiFetch<PaginatedDocuments>("/api/v1/documents", {
      query: {
        skip: options.skip,
        limit: PAGE_SIZE,
        search: options.search,
        document_type: options.documentType,
        status: options.status,
        confidentiality: options.confidentiality,
        visibility: options.visibility,
        legal_hold: options.legalHold || undefined,
      },
    });
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) redirect("/login");
    return null;
  }
}
