import Link from "next/link";
import { redirect } from "next/navigation";

import { DeactivateLawyerButton, LawyerForm } from "@/components/admin/abogados/lawyer-form";
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
import { createLawyer, deactivateLawyer } from "@/features/abogados/actions";
import { ApiNotAuthenticated, apiFetch } from "@/lib/api";
import { requireSession } from "@/lib/session-guard";
import type { LegalAreaOption, PaginatedLawyers } from "@/lib/types";

/**
 * The firm.
 *
 * `legal-areas` is loaded on every render because the create dialog needs the
 * catalogue to draw its checkboxes. It is twelve rows of reference data that
 * changes when the firm decides to add a practice area, which is not a request
 * worth caching across a session.
 */

const PAGE_SIZE = 25;

export default async function LawyersPage({
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
  const includeInactive = first(params.include_inactive) === "1";
  const skip = Math.max(0, Number(first(params.skip) ?? "0") || 0);

  const { value, failed } = await fetchLawyers({
    search,
    status,
    includeInactive,
    skip,
  });

  const areas = await apiFetch<LegalAreaOption[]>("/api/v1/lawyers/legal-areas").catch(
    () => [] as LegalAreaOption[],
  );

  const lawyers = value?.items ?? [];
  const total = value?.total ?? 0;

  const hrefFor = (next: Record<string, string | number>) => {
    const query = new URLSearchParams();
    if (search) query.set("search", search);
    if (status) query.set("status", status);
    if (includeInactive) query.set("include_inactive", "1");
    for (const [key, entry] of Object.entries(next)) query.set(key, String(entry));
    const text = query.toString();
    return text ? `/admin/abogados?${text}` : "/admin/abogados";
  };

  return (
    <div>
      <PageHeader
        eyebrow="Plantilla"
        title="Abogados"
        description="Profesionales de la firma, con su estado y sus áreas de práctica. Un abogado se desactiva, nunca se borra: sus expedientes siguen necesitando un responsable."
        actions={<LawyerForm action={createLawyer} areas={areas} legal />}
      />

      <FilterBar>
        <FilterField
          label="Buscar"
          name="search"
          defaultValue={search}
          placeholder="Nombre o número de documento"
          className="min-w-[16rem] flex-1"
        />
        <div>
          <label htmlFor="filtro-status" className="label-rule block">
            Estado
          </label>
          <select
            id="filtro-status"
            name="status"
            defaultValue={status ?? ""}
            className="mt-1.5 rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax"
          >
            <option value="">Todos</option>
            <option value="activo">Activo</option>
            <option value="inactivo">Inactivo</option>
            <option value="suspendido">Suspendido</option>
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
        {search || status || includeInactive ? (
          <Link
            href="/admin/abogados"
            className="pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted underline-offset-4 hover:text-wax hover:underline"
          >
            Limpiar
          </Link>
        ) : null}
      </FilterBar>

      {failed ? (
        <p className="mt-6 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
          No fue posible cargar el listado.
        </p>
      ) : null}

      <div className="mt-6">
        {lawyers.length === 0 ? (
          <EmptyState
            title="No hay abogados que coincidan"
            hint={
              search || status || includeInactive
                ? "Pruebe con otro texto o quite los filtros."
                : "Registre al primero con el botón «Nuevo abogado»."
            }
          />
        ) : (
          <Card className="overflow-hidden">
            {/* Six columns do not fit on a phone; the table scrolls inside its
                own card rather than being clipped. See the client list. */}
            <div className="overflow-x-auto">
              <table className="ledger min-w-[46rem]">
              <caption className="sr-only">
                Listado de abogados, {total} en total
              </caption>
              <thead>
                <tr>
                  <th scope="col" className="label-rule">
                    Profesional
                  </th>
                  <th scope="col" className="label-rule">
                    Documento
                  </th>
                  <th scope="col" className="label-rule">
                    Áreas
                  </th>
                  <th scope="col" className="label-rule">
                    Contacto
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
                {lawyers.map((lawyer, index) => (
                  <tr
                    key={lawyer.id}
                    data-accent={
                      !lawyer.is_active ? "closed" : lawyer.status === "suspendido" ? "held" : "live"
                    }
                    className="row-enter"
                    style={index < 8 ? { animationDelay: `${index * 12}ms` } : undefined}
                  >
                    <th scope="row" className="py-4 pr-4 font-normal">
                      <Link
                        href={`/admin/abogados/${lawyer.id}`}
                        className="row-title underline-offset-4 hover:underline"
                      >
                        {lawyer.full_name}
                      </Link>
                      {lawyer.professional_card ? (
                        <span className="row-meta mt-1 block">
                          T.P. {lawyer.professional_card}
                        </span>
                      ) : null}
                    </th>
                    <td className="row-meta py-4 pr-4">
                      {lawyer.document_type} {lawyer.document_number}
                    </td>
                    <td className="py-4 pr-4 text-[0.8125rem] text-ink-muted">
                      {lawyer.legal_areas.length > 0 ? (
                        lawyer.legal_areas.join(", ")
                      ) : (
                        <span className="text-ink-faint">—</span>
                      )}
                    </td>
                    <td className="py-4 pr-4 text-[0.8125rem] text-ink-muted">
                      {lawyer.email ?? <span className="text-ink-faint">—</span>}
                    </td>
                    <td className="py-4 pr-4">
                      <StatusChip status={lawyer.status} active={lawyer.is_active} />
                    </td>
                    <td className="py-4 text-right">
                      <div className="row-actions">
                        <Link
                          href={`/admin/abogados/${lawyer.id}`}
                          className="row-action-link"
                        >
                          <ActionIcon name="edit" />
                          Editar
                        </Link>
                        {lawyer.is_active ? (
                          <DeactivateLawyerButton
                            action={deactivateLawyer}
                            lawyerId={lawyer.id}
                            lawyerName={lawyer.full_name}
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
          Un abogado no se borra: se desactiva. Sus expedientes, documentos y
          evidencias se conservan, y deja de aparecer en la asignación de trabajo.
        </RuleNote>
      </div>
    </div>
  );
}

function StatusChip({
  status,
  active,
}: {
  status: string;
  active: boolean;
}) {
  if (!active) return <Chip tone="ink" dot>Desactivado</Chip>;
  if (status === "activo") return <Chip tone="forest" dot>Activo</Chip>;
  if (status === "suspendido") return <Chip tone="wax" dot>Suspendido</Chip>;
  return <Chip tone="brass" dot>Inactivo</Chip>;
}

function first(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}

async function fetchLawyers(options: {
  search?: string;
  status?: string;
  includeInactive: boolean;
  skip: number;
}): Promise<{ value: PaginatedLawyers | null; failed: boolean }> {
  try {
    return {
      value: await apiFetch<PaginatedLawyers>("/api/v1/lawyers", {
        query: {
          skip: options.skip,
          limit: PAGE_SIZE,
          search: options.search,
          status: options.status,
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
