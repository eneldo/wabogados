import Link from "next/link";
import { redirect } from "next/navigation";

import { ConsultationDetail } from "@/components/admin/solicitudes/consultation-detail";
import { Button } from "@/components/admin/form-controls";
import { FilterBar, PageHeader, Pager } from "@/components/admin/page-furniture";
import { Card, Chip, EmptyState, RuleNote } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { ApiNotAuthenticated, apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type {
  ConsultationRecord,
  ConsultationStatus,
  PaginatedConsultations,
} from "@/lib/types";

const PAGE_SIZE = 25;
const STATUS: Record<ConsultationStatus, { label: string; tone: "neutral" | "forest" | "brass" | "wax"; accent: string }> = {
  nueva: { label: "Nueva", tone: "wax", accent: "urgent" },
  en_revision: { label: "En revisión", tone: "brass", accent: "held" },
  atendida: { label: "Atendida", tone: "forest", accent: "live" },
  convertida: { label: "Convertida", tone: "forest", accent: "live" },
  descartada: { label: "Descartada", tone: "neutral", accent: "closed" },
};

export default async function SolicitudesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} backHref="/admin" />;
  }

  const can = (permission: string) => session.profile.permissions.includes(permission);
  if (!can("consultations:read")) {
    return (
      <div>
        <PageHeader eyebrow="Admisión" title="Solicitudes" description="Su perfil no tiene permiso para consultar las solicitudes recibidas desde la web pública." />
        <div className="mt-6"><EmptyState title="Sin acceso a esta sección" hint="Consulte con un administrador si necesita gestionar la admisión de consultas." /></div>
      </div>
    );
  }

  const params = await searchParams;
  const rawStatus = first(params.estado);
  const status = rawStatus && rawStatus in STATUS ? rawStatus as ConsultationStatus : undefined;
  const skip = Math.max(0, Number(first(params.skip) ?? "0") || 0);
  const open = first(params.solicitud);
  const { value, failed } = await load<PaginatedConsultations>("/api/v1/consultations", {
    skip,
    limit: PAGE_SIZE,
    status,
  });
  const items = value?.items ?? [];
  const total = value?.total ?? 0;
  const detailResult: { value: ConsultationRecord | null; failed: boolean } = open
    ? await load<ConsultationRecord>(`/api/v1/consultations/${encodeURIComponent(open)}`)
    : { value: null, failed: false };
  const detail = detailResult.value;

  const hrefFor = (next: { estado?: string; solicitud?: string; skip?: number }) => {
    const query = new URLSearchParams();
    const nextStatus = next.estado ?? status;
    const nextOpen = next.solicitud ?? open;
    if (nextStatus) query.set("estado", nextStatus);
    if (nextOpen) query.set("solicitud", nextOpen);
    if (next.skip) query.set("skip", String(next.skip));
    return query.size ? `/admin/solicitudes?${query.toString()}` : "/admin/solicitudes";
  };

  return (
    <div>
      <PageHeader
        eyebrow="Admisión"
        title="Solicitudes"
        description="Consultas enviadas desde la web pública. Contienen datos personales y una descripción jurídica: se revisan aquí, no se comparten. Descartar conserva la solicitud; eliminar solo corresponde a una petición expresa del titular."
      />

      <FilterBar>
        <div>
          <label htmlFor="filtro-estado" className="label-rule block">Estado</label>
          <select id="filtro-estado" name="estado" defaultValue={status ?? ""} className="mt-1.5 rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax">
            <option value="">Todos</option>
            <option value="nueva">Nueva</option>
            <option value="en_revision">En revisión</option>
            <option value="atendida">Atendida</option>
            <option value="convertida">Convertida</option>
            <option value="descartada">Descartada</option>
          </select>
        </div>
        <Button type="submit" variant="secondary">Filtrar</Button>
        {status ? <Link href="/admin/solicitudes" className="pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted underline-offset-4 hover:text-wax hover:underline">Limpiar</Link> : null}
      </FilterBar>

      {failed ? (
        <p className="mt-6 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">No fue posible cargar la cola. No se presenta como vacía porque el servicio no confirmó que lo esté.</p>
      ) : null}

      <div className="mt-6">
        {!failed && items.length === 0 ? (
          <EmptyState
            title={status ? "Ninguna solicitud coincide" : "No hay solicitudes pendientes"}
            hint={status ? "Cambie el estado o quite el filtro." : "Las nuevas consultas enviadas desde la web pública aparecerán aquí."}
          />
        ) : items.length > 0 ? (
          <>
            <Card className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="ledger min-w-[58rem]">
                  <caption className="sr-only">Cola de solicitudes, {total} registros en total</caption>
                  <thead><tr><th scope="col" className="label-rule">Persona</th><th scope="col" className="label-rule">Área</th><th scope="col" className="label-rule">Estado</th><th scope="col" className="label-rule">Recibida</th><th scope="col" className="label-rule">Atendida</th><th scope="col" className="label-rule text-right">Acciones</th></tr></thead>
                  <tbody>{items.map((item) => <ConsultationRow key={item.id} item={item} href={hrefFor({ solicitud: item.id })} />)}</tbody>
                </table>
              </div>
            </Card>
            <Pager total={total} skip={skip} limit={PAGE_SIZE} pageHref={(next) => hrefFor({ skip: next, solicitud: "" })} />
          </>
        ) : null}

        <RuleNote>Eliminar no es una acción ordinaria de la cola. «Descartada» conserva el registro; el borrado físico se reserva a una petición de supresión del titular y requiere el permiso específico consultations:erase.</RuleNote>
      </div>

      {detail ? (
        <ConsultationDetail item={detail} canUpdate={can("consultations:update")} canErase={can("consultations:erase")} closeHref={hrefFor({ solicitud: "" })} />
      ) : null}
    </div>
  );
}

function ConsultationRow({ item, href }: { item: ConsultationRecord; href: string }) {
  const presentation = STATUS[item.status];
  return (
    <tr data-accent={presentation.accent} className="row-enter">
      <th scope="row" className="py-4 pr-4 font-normal">
        <Link href={href} className="row-title block hover:text-wax hover:underline">{item.full_name}</Link>
        <span className="mt-1 block text-xs text-ink-muted">{item.email}</span>
        <span className="block text-xs text-ink-faint">{item.phone}</span>
      </th>
      <td className="max-w-48 py-4 pr-4 align-top text-sm text-ink-muted">{item.area}</td>
      <td className="py-4 pr-4 align-top"><Chip tone={presentation.tone}>{presentation.label}</Chip></td>
      <td className="row-meta py-4 pr-4 align-top">{formatDateTime(item.created_at)}</td>
      <td className="row-meta py-4 pr-4 align-top">{item.handled_at ? formatDateTime(item.handled_at) : "Sin atender"}</td>
      <td className="py-4 text-right align-top"><Link href={href} className="inline-flex rounded-card border border-rule px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted hover:border-wax hover:text-wax">Abrir</Link></td>
    </tr>
  );
}

async function load<T>(path: string, query: Record<string, string | number | undefined> = {}): Promise<{ value: T | null; failed: boolean }> {
  try {
    return { value: await apiFetch<T>(path, { query }), failed: false };
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) redirect("/login");
    return { value: null, failed: true };
  }
}

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}
