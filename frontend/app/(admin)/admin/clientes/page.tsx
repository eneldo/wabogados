import Link from "next/link";
import { redirect } from "next/navigation";

import { ClientForm, DeactivateButton } from "@/components/admin/clientes/client-form";
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
import { createClient, deactivateClient } from "@/features/clientes/actions";
import { ApiNotAuthenticated, apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type { PaginatedClients } from "@/lib/types";

/**
 * The client book.
 *
 * A plain GET form for the filters and a table for the results. No client
 * component owns the list: the filtered view is a URL, so it can be pasted into
 * a message and the back button behaves.
 *
 * The deactivation button lives on the row **and** on the detail screen. It used
 * to live only on the detail screen, on the argument that twenty rows with twenty
 * "Desactivar" buttons are twenty chances to destroy something. The firm asked
 * for the whole CRUD from the listing, and the original concern is answered by
 * keeping the confirmation: the row button opens a dialog that says what happens
 * and why nothing is deleted, and the destructive button never takes the initial
 * focus.
 */

const PAGE_SIZE = 25;

export default async function ClientsPage({
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
  const clientType = first(params.client_type);
  const includeInactive = first(params.include_inactive) === "1";
  const skip = Math.max(0, Number(first(params.skip) ?? "0") || 0);

  const { value, failed } = await fetchClients({
    search,
    clientType,
    includeInactive,
    skip,
  });

  const clients = value?.items ?? [];
  const total = value?.total ?? 0;

  const hrefFor = (next: Partial<Record<string, string | number>>) => {
    const query = new URLSearchParams();
    if (search) query.set("search", search);
    if (clientType) query.set("client_type", clientType);
    if (includeInactive) query.set("include_inactive", "1");
    for (const [key, entry] of Object.entries(next)) query.set(key, String(entry));
    const text = query.toString();
    return text ? `/admin/clientes?${text}` : "/admin/clientes";
  };

  return (
    <div>
      <PageHeader
        eyebrow="Cartera"
        title="Clientes"
        description="Registro de personas naturales y jurídicas. Un cliente se desactiva, nunca se borra: sus expedientes y evidencias deben seguir existiendo después de que deje de ser cliente."
        actions={<ClientForm action={createClient} legal />}
      />

      <FilterBar>
        <FilterField
          label="Buscar"
          name="search"
          defaultValue={search}
          placeholder="Nombre, razón social o documento"
          className="min-w-[16rem] flex-1"
        />
        <div>
          <label htmlFor="filtro-client_type" className="label-rule block">
            Tipo
          </label>
          <select
            id="filtro-client_type"
            name="client_type"
            defaultValue={clientType ?? ""}
            className="mt-1.5 rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax"
          >
            <option value="">Todos</option>
            <option value="natural">Persona natural</option>
            <option value="juridica">Persona jurídica</option>
          </select>
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm text-ink-soft">
          <input
            type="checkbox"
            name="include_inactive"
            value="1"
            defaultChecked={includeInactive}
            className="size-4 accent-wax"
          />
          Incluir inactivos
        </label>
        <Button type="submit" variant="secondary">
          Filtrar
        </Button>
        {search || clientType || includeInactive ? (
          <Link
            href="/admin/clientes"
            className="pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted underline-offset-4 hover:text-wax hover:underline"
          >
            Limpiar
          </Link>
        ) : null}
      </FilterBar>

      {failed ? (
        <p className="mt-6 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
          No fue posible cargar el listado. Los datos mostrados abajo pueden estar
          incompletos.
        </p>
      ) : null}

      <div className="mt-6">
        {clients.length === 0 ? (
          <EmptyState
            title="No hay clientes que coincidan"
            hint={
              search || clientType || includeInactive
                ? "Pruebe con otro texto o quite los filtros."
                : "Registre el primero con el botón «Nuevo cliente»."
            }
          />
        ) : (
          <Card className="overflow-hidden">
            {/*
              `overflow-x-auto`, not `overflow-hidden`. Six columns of identity
              data do not fit on a phone, and clipping them would delete the
              document number and the state without saying so — the reader would
              see a shortened table and conclude that was all there was. The
              table scrolls inside its own card and the page never moves.
            */}
            <div className="overflow-x-auto">
              <table className="ledger min-w-[46rem]">
              <caption className="sr-only">
                Listado de clientes, {total} en total
              </caption>
              <thead>
                <tr>
                  <th scope="col" className="label-rule">
                    Cliente
                  </th>
                  <th scope="col" className="label-rule">
                    Documento
                  </th>
                  <th scope="col" className="label-rule">
                    Contacto
                  </th>
                  <th scope="col" className="label-rule">
                    Estado
                  </th>
                  <th scope="col" className="label-rule">
                    Alta
                  </th>
                  <th scope="col" className="label-rule text-right">
                    <span className="sr-only">Acciones</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {clients.map((client, index) => (
                  <tr
                    key={client.id}
                    /* Active clients wear the forest rule; a deactivated one is
                       history and stays a plain ledger line. */
                    data-accent={client.is_active ? "live" : "closed"}
                    className="row-enter"
                    style={index < 8 ? { animationDelay: `${index * 12}ms` } : undefined}
                  >
                    <th scope="row" className="py-4 pr-4 font-normal">
                      <Link
                        href={`/admin/clientes/${client.id}`}
                        className="row-title underline-offset-4 hover:underline"
                      >
                        {client.display_name}
                      </Link>
                      <span className="mt-1 block text-xs text-ink-faint">
                        {client.client_type === "juridica" ? "Persona jurídica" : "Persona natural"}
                      </span>
                    </th>
                    <td className="row-meta py-4 pr-4">
                      {client.document_type} {client.document_number}
                    </td>
                    <td className="py-4 pr-4 text-[0.8125rem] text-ink-muted">
                      {client.email ?? <span className="text-ink-faint">—</span>}
                      <span className="mt-0.5 block text-xs text-ink-faint">
                        {client.phone ?? ""}
                      </span>
                    </td>
                    <td className="py-4 pr-4">
                      {client.is_active ? (
                        <Chip tone="forest" dot>
                          Activo
                        </Chip>
                      ) : (
                        <Chip tone="ink" dot>
                          Inactivo
                        </Chip>
                      )}
                    </td>
                    <td className="row-meta py-4 pr-4">
                      {formatDate(client.created_at)}
                    </td>
                    <td className="py-4 text-right">
                      <div className="row-actions">
                        <Link
                          href={`/admin/clientes/${client.id}`}
                          className="row-action-link"
                        >
                          <ActionIcon name="edit" />
                          Editar
                        </Link>
                        {client.is_active ? (
                          <DeactivateButton
                            action={deactivateClient}
                            clientId={client.id}
                            clientName={client.display_name}
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
          Un cliente no se borra: se desactiva. Sus expedientes, documentos y
          evidencias se conservan, que es lo que un expediente abierto exige.
        </RuleNote>
      </div>
    </div>
  );
}

function first(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}

/**
 * The list, or an admission that it could not be loaded.
 *
 * `failed` is separate from `value` on purpose. A list that silently renders as
 * empty is the worst outcome available here: an administrator would conclude
 * the firm has no clients. An empty list and a failed list must never look alike.
 */
async function fetchClients(options: {
  search?: string;
  clientType?: string;
  includeInactive: boolean;
  skip: number;
}): Promise<{ value: PaginatedClients | null; failed: boolean }> {
  try {
    return {
      value: await apiFetch<PaginatedClients>("/api/v1/clients", {
        query: {
          skip: options.skip,
          limit: PAGE_SIZE,
          search: options.search,
          client_type: options.clientType,
          include_inactive: options.includeInactive || undefined,
        },
      }),
      failed: false,
    };
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) redirect("/login");
    return { value: null, failed: true };
  }
}
