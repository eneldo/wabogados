import Link from "next/link";
import { redirect } from "next/navigation";

import { Button } from "@/components/admin/form-controls";
import { FilterBar, FilterField, PageHeader, Pager } from "@/components/admin/page-furniture";
import { Card, Chip, EmptyState, RuleNote } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { ApiNotAuthenticated, apiFetch } from "@/lib/api";
import {
  auditActionParts,
  auditResultLabel,
  auditResultTone,
  formatDateTime,
  humanise,
} from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type { AuditLogRecord, PaginatedAuditLogs, PaginatedUsers } from "@/lib/types";

const PAGE_SIZE = 25;

export default async function SecurityAuditPage({
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
  const params = await searchParams;
  const vista = first(params.vista);

  if (vista === "usuarios") redirect("/admin/usuarios");
  if (vista === "roles") redirect("/admin/roles");

  if (!can("audit_logs:read")) {
    return (
      <div>
        <PageHeader
          eyebrow="Seguridad"
          title="Auditoría"
          description="Su perfil no tiene permiso para consultar la auditoría. La gestión de usuarios y roles está disponible en sus módulos dedicados."
        />
        <div className="mt-6 flex flex-wrap gap-3">
          {can("users:read") ? <Link className="text-sm font-semibold text-wax underline-offset-4 hover:underline" href="/admin/usuarios">Ir a Usuarios</Link> : null}
          {can("roles:read") ? <Link className="text-sm font-semibold text-wax underline-offset-4 hover:underline" href="/admin/roles">Ir a Roles</Link> : null}
        </div>
        <div className="mt-6">
          <EmptyState
            title="Sin acceso a auditoría"
            hint="Consulte con un administrador si necesita revisar el registro de operaciones."
          />
        </div>
      </div>
    );
  }

  const q = first(params.q);
  const resultado = first(params.resultado);
  const actor = first(params.actor);
  const skip = Math.max(0, Number(first(params.skip) ?? "0") || 0);
  const filters = { q, resultado, actor };

  const { value, failed } = await load<PaginatedAuditLogs>("/api/v1/admin/audit-logs", {
    skip,
    limit: PAGE_SIZE,
    search: q,
    result: resultado || undefined,
    user_id: actor,
  });

  const entries = value?.items ?? [];
  const total = value?.total ?? 0;

  const actorOptions = can("users:read")
    ? ((await load<PaginatedUsers>("/api/v1/admin/users", { skip: 0, limit: 200 })).value?.items ?? [])
    : [];

  const hrefFor = (next: Record<string, string | number | undefined> = {}) => {
    const query = new URLSearchParams();
    for (const [key, val] of Object.entries(filters)) {
      if (val) query.set(key, val);
    }
    for (const [key, val] of Object.entries(next)) {
      if (val !== undefined && val !== "") query.set(key, String(val));
    }
    const qs = query.toString();
    return qs ? `/admin/seguridad?${qs}` : "/admin/seguridad";
  };

  return (
    <div>
      <PageHeader
        eyebrow="Seguridad"
        title="Auditoría"
        description="Registro de operaciones de escritura: quién hizo qué, cuándo, desde dónde y con qué resultado. La gestión de usuarios y roles se realiza en sus módulos dedicados."
      />

      <div className="mt-6 flex flex-wrap gap-3 text-sm">
        {can("users:read") ? <Link className="font-semibold text-wax underline-offset-4 hover:underline" href="/admin/usuarios">Módulo Usuarios</Link> : null}
        {can("roles:read") ? <Link className="font-semibold text-wax underline-offset-4 hover:underline" href="/admin/roles">Módulo Roles</Link> : null}
      </div>

      <div className="mt-6">
        <FilterBar>
          <FilterField
            label="Buscar"
            name="q"
            defaultValue={q}
            placeholder="Acción o entidad"
            className="min-w-[14rem] flex-1"
          />
          <div>
            <label htmlFor="filtro-result" className="label-rule block">Resultado</label>
            <select
              id="filtro-result"
              name="resultado"
              defaultValue={resultado ?? ""}
              className="mt-1.5 rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax"
            >
              <option value="">Todos</option>
              <option value="success">Correcto</option>
              <option value="error">Error</option>
            </select>
          </div>
          {actorOptions.length > 0 ? (
            <div>
              <label htmlFor="filtro-actor" className="label-rule block">Quién</label>
              <select
                id="filtro-actor"
                name="actor"
                defaultValue={actor ?? ""}
                className="mt-1.5 rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax"
              >
                <option value="">Cualquiera</option>
                {actorOptions.map((user) => (
                  <option key={user.id} value={user.id}>{user.email}</option>
                ))}
              </select>
            </div>
          ) : null}
          <Button type="submit" variant="secondary">Filtrar</Button>
          {q || resultado || actor ? (
            <Link
              href="/admin/seguridad"
              className="pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted underline-offset-4 hover:text-wax hover:underline"
            >
              Limpiar
            </Link>
          ) : null}
        </FilterBar>

        {failed ? (
          <p className="mt-6 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
            No fue posible cargar la auditoría. Sin este registro la pantalla no puede responder quién hizo qué.
          </p>
        ) : null}

        <div className="mt-6">
          {entries.length === 0 ? (
            <EmptyState
              title="Sin entradas de auditoría"
              hint={q || resultado || actor ? "Pruebe con otro texto o quite los filtros." : "Todavía no se ha registrado ninguna operación de escritura."}
            />
          ) : (
            <Card className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="ledger min-w-[58rem]">
                  <caption className="sr-only">Registro de auditoría, {total} entradas</caption>
                  <thead>
                    <tr>
                      <th scope="col" className="label-rule">Momento</th>
                      <th scope="col" className="label-rule">Quién</th>
                      <th scope="col" className="label-rule">Acción</th>
                      <th scope="col" className="label-rule">Entidad</th>
                      <th scope="col" className="label-rule">Resultado</th>
                      <th scope="col" className="label-rule">Origen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entries.map((entry, index) => (
                      <AuditRow key={entry.id} entry={entry} index={index} />
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
            pageHref={(next) => hrefFor({ ...filters, skip: next })}
          />

          <RuleNote>
            La auditoría guarda la operación, no su contenido. Las lecturas no se registran.
          </RuleNote>
        </div>
      </div>
    </div>
  );
}

function AuditRow({ entry, index }: { entry: AuditLogRecord; index: number }) {
  const [method, path] = auditActionParts(entry.action);

  return (
    <tr
      data-accent={entry.result === "success" ? "live" : "urgent"}
      className="row-enter"
      style={index < 8 ? { animationDelay: `${index * 12}ms` } : undefined}
    >
      <td className="row-meta py-4 pr-4">{formatDateTime(entry.created_at)}</td>
      <td className="py-4 pr-4 text-[0.8125rem] text-ink-muted">
        {entry.user_email ?? <span className="text-ink-faint">Sin usuario</span>}
      </td>
      <td className="py-4 pr-4">
        <Chip tone={method === "DELETE" ? "wax" : "neutral"}>{method}</Chip>
        <span className="mt-1 block break-all font-mono text-[0.6875rem] text-ink-faint">{path}</span>
      </td>
      <td className="py-4 pr-4 text-[0.8125rem] text-ink-muted">
        {humanise(entry.entity)}
        {entry.entity_id ? (
          <span className="mt-0.5 block font-mono text-[0.6875rem] text-ink-faint">{entry.entity_id.slice(0, 8)}</span>
        ) : null}
      </td>
      <td className="py-4 pr-4">
        <Chip tone={auditResultTone(entry.result)} dot>{auditResultLabel(entry.result)}</Chip>
      </td>
      <td className="py-4 text-[0.8125rem] text-ink-muted">
        {entry.ip_address ?? <span className="text-ink-faint">—</span>}
        {entry.user_agent ? (
          <span className="mt-0.5 block max-w-[14rem] truncate text-xs text-ink-faint">{entry.user_agent}</span>
        ) : null}
      </td>
    </tr>
  );
}

function first(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}

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
