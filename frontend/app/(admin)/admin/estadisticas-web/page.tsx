import Link from "next/link";
import { redirect } from "next/navigation";

import { PageHeader } from "@/components/admin/page-furniture";
import { Card, EmptyState, RuleNote } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { apiFetch, ApiRequestError } from "@/lib/api";
import { getPublicServices } from "@/lib/public-services.server";
import { requireSession } from "@/lib/session-guard";
import type { WebsiteCounts, WebsitePage, WebsiteSummary } from "@/lib/website-analytics";

const number = (value: number) => value.toLocaleString("es-CO");

export default async function WebsiteAnalyticsPage({ searchParams }: {
  searchParams: Promise<{ start?: string; end?: string }>;
}) {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") return <ServiceUnavailable message={session.message} backHref="/admin" />;
  if (!session.profile.permissions.includes("website_analytics:read")) {
    return <EmptyState title="Acceso restringido" hint="Su perfil no tiene permiso para consultar estadísticas web." />;
  }
  const params = await searchParams;
  let data: WebsiteSummary;
  try {
    data = await apiFetch<WebsiteSummary>("/api/v1/admin/metrics/website", {
      query: { start: params.start, end: params.end },
    });
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 422) {
      return <div className="space-y-6"><PageHeader eyebrow="Web pública" title="Estadísticas web" /><EmptyState title="Rango de fechas no válido" hint="Seleccione hasta 366 días, sin fechas futuras." /><Link href="/admin/estadisticas-web" className="text-wax underline">Restablecer fechas</Link></div>;
    }
    return <ServiceUnavailable message="No fue posible cargar las estadísticas. No se mostrarán ceros ficticios." backHref="/admin" />;
  }
  const { services } = await getPublicServices();
  const names = new Map(services.map((service) => [`/servicios/${service.slug}`, service.title]));
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "America/Bogota" });
  const maximum = Math.max(1, ...data.daily.map((item) => item.page_views));
  const kpis = [
    ["Páginas vistas", data.totals.page_views],
    ["Visitantes estimados · suma diaria", data.totals.estimated_visitors],
    ["Clics en teléfono", data.totals.phone_clicks],
    ["Solicitudes registradas", data.totals.consultations],
  ] as const;

  return (
    <div className="space-y-7">
      <PageHeader eyebrow="Web pública · privado" title="Estadísticas web" description="Visitas y contactos de la página oficial. Sin cookies, huellas del dispositivo ni seguimiento de expedientes." />
      <Card className="p-5">
        <form method="get" className="flex flex-wrap items-end gap-4" aria-label="Periodo de estadísticas">
          <label className="min-w-0 text-sm">Desde<input type="date" name="start" defaultValue={data.start} max={today} required className="mt-2 block max-w-full rounded-card border border-rule bg-canvas px-3 py-2" /></label>
          <label className="min-w-0 text-sm">Hasta<input type="date" name="end" defaultValue={data.end} max={today} required className="mt-2 block max-w-full rounded-card border border-rule bg-canvas px-3 py-2" /></label>
          <button type="submit" className="rounded-card bg-action px-5 py-2.5 text-sm font-semibold text-on-action">Aplicar periodo</button>
        </form>
        <p className="mt-3 text-xs text-ink-muted">Zona horaria: {data.timezone}. Hasta 366 días por consulta; agregados conservados durante 400 días.</p>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map(([label, value]) => <Card key={label} className="p-5"><p className="font-display text-4xl">{number(value)}</p><p className="label-rule mt-3">{label}</p></Card>)}
      </div>
      <RuleNote>
        Los visitantes son navegaciones anónimas estimadas, no personas identificadas. Una recarga o una nueva pestaña puede contar de nuevo. Los totales del periodo suman estimaciones diarias, no visitantes únicos mensuales. Los clics no acreditan una llamada completada; las solicitudes solo cuentan cuando se registran en el servidor. No hay datos anteriores a la activación.
      </RuleNote>

      {data.totals.page_views === 0 ? <EmptyState title="Aún no hay visitas registradas en este periodo" hint="No se incluyen navegadores que rechacen el seguimiento, bloqueen el script o tengan JavaScript desactivado." /> : (
        <Card className="p-6">
          <h2 className="font-display text-xl">Evolución diaria · páginas vistas</h2>
          <div role="img" aria-label={`Páginas vistas entre ${data.start} y ${data.end}; valores exactos en la tabla diaria.`} className="mt-6 flex h-40 items-end gap-px border-b border-rule">
            {data.daily.map((item) => <div key={item.day} title={`${item.day}: ${item.page_views}`} className="min-w-0 flex-1 bg-wax" style={{ height: `${item.page_views === 0 ? 0 : Math.max(2, item.page_views / maximum * 100)}%` }} />)}
          </div>
          <div className="mt-2 flex justify-between gap-3 text-xs text-ink-muted"><span>{data.start}</span><span>{data.end}</span></div>
        </Card>
      )}

      <div className="grid items-start gap-5 xl:grid-cols-2">
        <PageList title="Áreas jurídicas más consultadas" items={data.areas} names={names} />
        <PageList title="Páginas públicas más vistas" items={data.pages} names={names} />
      </div>
      <Card className="p-5 sm:p-6">
        <h2 className="font-display text-xl">Evolución por mes</h2>
        <CountsTable rows={data.monthly.map((row) => ({ label: row.month, ...row }))} heading="Mes" />
        <details className="mt-7">
          <summary className="cursor-pointer text-sm text-wax">Ver detalle diario ({data.daily.length} días)</summary>
          <CountsTable rows={data.daily.map((row) => ({ label: row.day, ...row }))} heading="Día" />
        </details>
      </Card>
      <RuleNote>Se respetan Do Not Track y Global Privacy Control. Los identificadores aleatorios solo viven en memoria del navegador; las huellas de deduplicación caducan a las 48 horas y se purgan automáticamente cada hora. No se guardan IP, nombres, correos, textos de consulta, cadenas de búsqueda ni referentes en la analítica.</RuleNote>
    </div>
  );
}

function PageList({ title, items, names }: { title: string; items: WebsitePage[]; names: Map<string, string> }) {
  return <Card className="p-5 sm:p-6"><h2 className="font-display text-xl">{title}</h2>{items.length === 0 ? <p className="mt-5 text-sm text-ink-muted">Sin datos en este periodo.</p> : <ul className="mt-5 divide-y divide-rule">{items.map((item) => <li key={item.path} className="flex items-start justify-between gap-4 py-3"><div className="min-w-0"><Link href={item.path} className="break-words text-sm hover:text-wax">{item.path === "/" ? "Página principal" : names.get(item.path) ?? item.path}</Link><p className="mt-1 text-xs text-ink-muted">{number(item.phone_clicks)} clics en teléfono</p></div><span className="tnum shrink-0 text-sm">{number(item.page_views)} vistas</span></li>)}</ul>}</Card>;
}

function CountsTable({ rows, heading }: { rows: (WebsiteCounts & { label: string })[]; heading: string }) {
  return <div className="mt-5 max-h-96 overflow-auto"><table className="ledger min-w-[600px] text-sm"><caption className="sr-only">Vistas, estimaciones diarias de visitantes acumuladas, clics y solicitudes por {heading.toLowerCase()}</caption><thead><tr>{[heading, "Vistas", "Visitantes estimados*", "Clics teléfono", "Solicitudes"].map((title) => <th key={title} scope="col" className="px-3">{title}</th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.label}><th scope="row" className="px-3 py-3 text-left font-normal">{row.label}</th>{[row.page_views, row.estimated_visitors, row.phone_clicks, row.consultations].map((value, index) => <td key={index} className="tnum px-3 py-3">{number(value)}</td>)}</tr>)}</tbody></table></div>;
}
