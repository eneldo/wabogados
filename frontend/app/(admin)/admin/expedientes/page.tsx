import Link from "next/link";
import { redirect } from "next/navigation";

import { CaseForm, CloseCaseButton } from "@/components/admin/expedientes/case-form";
import {
  FilterBar,
  FilterField,
  PageHeader,
  Pager,
} from "@/components/admin/page-furniture";
import { Button } from "@/components/admin/form-controls";
import { ActionIcon } from "@/components/admin/icons";
import { Card, Chip, EmptyState, RuleNote } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { closeCase, createCase } from "@/features/expedientes/actions";
import { ApiNotAuthenticated, apiFetch } from "@/lib/api";
import {
  caseStatusLabel,
  caseStatusTone,
  formatDate,
  priorityLabel,
  priorityTone,
  processTypeLabel,
} from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type {
  CaseOption,
  LegalAreaOption,
  PaginatedCases,
} from "@/lib/types";

/**
 * The case book.
 *
 * Reuses `/expedientes`? No — that page reads the **dashboard**, which is capped
 * at a handful of rows and only what the caller's scope allows. A firm's book
 * needs `/cases` with its filters, and this is that query. The lawyer's own
 * shortlist stays where it is.
 *
 * Note what is absent: a "Eliminar" button. A case is the definition of a legal
 * record, so its lifecycle ends at `cerrado` and never at deletion.
 */

const PAGE_SIZE = 25;

/**
 * What colour the row's left rule wears.
 *
 * One rule, one question: does this row need me today? A case that is closed is
 * history and stays a plain ledger line; a suspended case is waiting on someone
 * and wears brass; an urgent one is the only thing on the screen that wears wax,
 * which is why it is the only red on the page. Everything else is live, and live
 * wears forest because that is the colour the rest of the system already means by
 * "verified, in progress, intact".
 */
function rowAccent(record: { status: string; priority: string }): string {
  if (record.status === "cerrado" || record.status === "archivado") return "closed";
  if (record.priority === "urgente") return "urgent";
  if (record.status === "suspendido") return "held";
  return "live";
}

export default async function CasesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} backHref="/admin" />;
  }

  const params = await searchParams;
  const search = first(params.search);
  const status = first(params.status);
  const priority = first(params.priority);
  const processType = first(params.process_type);
  const openOnly = first(params.open_only) === "1";
  const skip = Math.max(0, Number(first(params.skip) ?? "0") || 0);

  const [{ value, failed }, clients, lawyers, areas] = await Promise.all([
    fetchCases({ search, status, priority, processType, openOnly, skip }),
    apiFetch<PaginatedClientsLite>("/api/v1/clients", {
      query: { skip: 0, limit: 200, include_inactive: 1 },
    }).catch(() => ({ items: [] })),
    apiFetch<{ items: LawyerLite[] }>("/api/v1/lawyers", {
      query: { skip: 0, limit: 200, status: "activo" },
    }).catch(() => ({ items: [] })),
    apiFetch<LegalAreaOption[]>("/api/v1/lawyers/legal-areas").catch(() => []),
  ]);

  const cases = value?.items ?? [];
  const total = value?.total ?? 0;

  const clientOptions: CaseOption[] = (clients.items ?? []).map((c) => ({
    id: c.id,
    label: c.display_name,
  }));
  const lawyerOptions: CaseOption[] = (lawyers.items ?? []).map((l) => ({
    id: l.id,
    label: l.full_name,
  }));
  const areaOptions: CaseOption[] = areas.map((a) => ({ id: a.id, label: a.name }));

  const hrefFor = (next: Record<string, string | number>) => {
    const query = new URLSearchParams();
    if (search) query.set("search", search);
    if (status) query.set("status", status);
    if (priority) query.set("priority", priority);
    if (processType) query.set("process_type", processType);
    if (openOnly) query.set("open_only", "1");
    for (const [key, value] of Object.entries(next)) query.set(key, String(value));
    const text = query.toString();
    return text ? `/admin/expedientes?${text}` : "/admin/expedientes";
  };

  const filtered =
    Boolean(search || status || priority || processType || openOnly);

  return (
    <div>
      <PageHeader
        eyebrow="Cartera"
        title="Expedientes"
        description="Todos los asuntos de la firma. Un expediente no se borra: se cierra, y su historial queda abierto para consulta."
        actions={
          <CaseForm
            action={createCase}
            clients={clientOptions}
            lawyers={lawyerOptions}
            areas={areaOptions}
            legal
          />
        }
      />

      <FilterBar>
        <FilterField
          label="Buscar"
          name="search"
          defaultValue={search}
          placeholder="Título, número o cliente"
          className="min-w-[15rem] flex-1"
        />

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
            <option value="abierto">Abierto</option>
            <option value="en_tramitacion">En tramitación</option>
            <option value="suspendido">Suspendido</option>
            <option value="cerrado">Cerrado</option>
            <option value="archivado">Archivado</option>
          </select>
        </div>

        <div>
          <label htmlFor="filtro-process_type" className="label-rule block">
            Proceso
          </label>
          <select
            id="filtro-process_type"
            name="process_type"
            defaultValue={processType ?? ""}
            className={SELECT}
          >
            <option value="">Todos</option>
            {PROCESS_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="filtro-priority" className="label-rule block">
            Prioridad
          </label>
          <select
            id="filtro-priority"
            name="priority"
            defaultValue={priority ?? ""}
            className={SELECT}
          >
            <option value="">Todas</option>
            <option value="baja">Baja</option>
            <option value="normal">Normal</option>
            <option value="alta">Alta</option>
            <option value="urgente">Urgente</option>
          </select>
        </div>

        <label className="flex items-center gap-2 pb-2 text-sm text-ink-soft">
          <input
            type="checkbox"
            name="open_only"
            value="1"
            defaultChecked={openOnly}
            className="size-4 accent-wax"
          />
          Solo abiertos
        </label>

        <Button type="submit" variant="secondary">
          Filtrar
        </Button>
        {filtered ? (
          <Link
            href="/admin/expedientes"
            className="pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted underline-offset-4 hover:text-wax hover:underline"
          >
            Limpiar
          </Link>
        ) : null}
      </FilterBar>

      {failed ? (
        <p className="mt-6 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
          No fue posible cargar el listado. Un listado vacío y un listado que falló
          no son lo mismo, y este aviso es la diferencia.
        </p>
      ) : null}

      <div className="mt-6">
        {cases.length === 0 ? (
          <EmptyState
            title={filtered ? "No hay expedientes que coincidan" : "No hay expedientes"}
            hint={
              filtered
                ? "Pruebe con otro texto o quite los filtros."
                : "Abra el primero con el botón «Nuevo expediente»."
            }
          />
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="ledger min-w-[52rem]">
                <caption className="sr-only">
                  Listado de expedientes, {total} en total
                </caption>
                <thead>
                  <tr>
                    <th scope="col" className="label-rule">
                      Expediente
                    </th>
                    <th scope="col" className="label-rule">
                      Cliente
                    </th>
                    <th scope="col" className="label-rule">
                      Proceso
                    </th>
                    <th scope="col" className="label-rule">
                      Responsable
                    </th>
                    <th scope="col" className="label-rule">
                      Prioridad
                    </th>
                    <th scope="col" className="label-rule">
                      Estado
                    </th>
                    <th scope="col" className="label-rule text-right">
                      <span className="sr-only">Acciones</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((record, index) => (
                    <tr
                      key={record.id}
                      data-accent={rowAccent(record)}
                      className="row-enter"
                      /* Only the first few rows are staggered; see globals.css. */
                      style={index < 8 ? { animationDelay: `${index * 12}ms` } : undefined}
                    >
                      <th scope="row" className="py-4 pr-4 font-normal">
                        <Link
                          href={`/admin/expedientes/${record.id}`}
                          className="row-title underline-offset-4 hover:underline"
                        >
                          {record.title}
                        </Link>
                        <span className="row-meta mt-1 block">
                          {record.case_number}
                          {record.file_number ? ` · ${record.file_number}` : ""}
                        </span>
                      </th>
                      <td className="py-4 pr-4 text-[0.8125rem] text-ink-muted">
                        {record.client_name}
                      </td>
                      <td className="py-4 pr-4 text-[0.8125rem] text-ink-muted">
                        {processTypeLabel(record.process_type)}
                        {record.legal_area_name ? (
                          <span className="mt-0.5 block text-xs text-ink-faint">
                            {record.legal_area_name}
                          </span>
                        ) : null}
                      </td>
                      <td className="py-4 pr-4 text-[0.8125rem] text-ink-muted">
                        {record.responsible_lawyer_name ?? (
                          <span className="text-ink-faint">Sin asignar</span>
                        )}
                      </td>
                      {/* One pill per row: the status. Priority is a dot. */}
                      <td className="py-4 pr-4">
                        <Chip tone={priorityTone(record.priority)} dot>
                          {priorityLabel(record.priority)}
                        </Chip>
                      </td>
                      <td className="py-4 pr-4">
                        <div className="flex flex-col items-start gap-1.5">
                          <Chip tone={caseStatusTone(record.status)}>
                            {caseStatusLabel(record.status)}
                          </Chip>
                          <span className="row-meta">
                            {record.closed_at
                              ? `Cerrado ${formatDate(record.closed_at)}`
                              : `Abierto ${formatDate(record.opened_at)}`}
                          </span>
                        </div>
                      </td>
                      <td className="py-4 text-right">
                        <div className="row-actions">
                          <Link
                            href={`/admin/expedientes/${record.id}`}
                            className="row-action-link"
                          >
                            <ActionIcon name="edit" />
                            Editar
                          </Link>
                          {record.status !== "cerrado" &&
                          record.status !== "archivado" ? (
                            <CloseCaseButton
                              action={closeCase}
                              caseId={record.id}
                              caseNumber={record.case_number}
                              triggerLabel="Cerrar"
                              idPrefix={`close-${record.case_number}`}
                              variant="quiet"
                            />
                          ) : null}
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
          Un expediente no se elimina. Si deja de estar activo, se cierra y queda
          como cerrado: todo su contenido sigue consultable.
        </RuleNote>
      </div>
    </div>
  );
}

const SELECT =
  "mt-1.5 rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax";

const PROCESS_TYPE_OPTIONS = [
  { value: "civil", label: "Civil" },
  { value: "penal", label: "Penal" },
  { value: "laboral", label: "Laboral" },
  { value: "administrativo", label: "Administrativo" },
  { value: "comercial", label: "Comercial" },
  { value: "familia", label: "Familia" },
  { value: "tributario", label: "Tributario" },
  { value: "arbitraje", label: "Arbitraje" },
  { value: "otro", label: "Otro" },
];

type PaginatedClientsLite = {
  items: Array<{ id: string; display_name: string }>;
};

type LawyerLite = { id: string; full_name: string };

function first(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}

async function fetchCases(options: {
  search?: string;
  status?: string;
  priority?: string;
  processType?: string;
  openOnly: boolean;
  skip: number;
}): Promise<{ value: PaginatedCases | null; failed: boolean }> {
  try {
    return {
      value: await apiFetch<PaginatedCases>("/api/v1/cases", {
        query: {
          skip: options.skip,
          limit: PAGE_SIZE,
          search: options.search,
          status: options.status,
          priority: options.priority,
          process_type: options.processType,
          open_only: options.openOnly || undefined,
        },
      }),
      failed: false,
    };
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) redirect("/login");
    return { value: null, failed: true };
  }
}
