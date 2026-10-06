import Link from "next/link";
import { redirect } from "next/navigation";

import { PageHeader } from "@/components/admin/page-furniture";
import { Card, Chip, EmptyState, RuleNote } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { apiFetchOr } from "@/lib/api";
import { formatDate, formatWhen } from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type { DashboardPayload } from "@/lib/types";

/**
 * The administration dashboard.
 *
 * It reuses `/api/v1/dashboard`, which the panel already reads. Two people
 * asking the same question should not produce two different numbers, and the
 * permission, the scoping and the shape of that endpoint are already decided.
 *
 * The figures are the backend's. Nothing here computes a rate, extrapolates a
 * trend or rounds a count into a percentage the API did not send: a dashboard
 * that invents a number is a dashboard nobody can defend in a meeting.
 */

export default async function AdminDashboardPage() {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} backHref="/" />;
  }

  const dashboard = await apiFetchOr<DashboardPayload | null>(
    null,
    "/api/v1/dashboard",
    { query: { limit: 8 } },
  ).catch(() => null);

  if (!dashboard) {
    return (
      <div>
        <PageHeader eyebrow="Resumen" title="Dashboard" />
        <div className="mt-6">
          <EmptyState
            title="No fue posible cargar el panel"
            hint="El servicio no respondió. Los datos de la firma no se han modificado."
          />
        </div>
      </div>
    );
  }

  const kpis = dashboard.kpis;
  /*
    The eight numbers, and what each one is *for*.

    A dashboard that shows every figure in the same voice shows no figure at all.
    Four of these count volume — how many clients, how many files, how many
    hearings are on the calendar — and four count work that is waiting. The
    second group gets a coloured rule at the top of its card, and wax only when
    there is actually something overdue: a red rule over a zero is a dashboard
    that cries wolf, and this one is read first thing every morning.
  */
  const cards = [
    { label: "Clientes activos", value: kpis.active_clients, rule: "bg-rule-strong" },
    { label: "Expedientes activos", value: kpis.active_cases, rule: "bg-forest" },
    { label: "Expedientes cerrados", value: kpis.closed_cases, rule: "bg-rule-strong" },
    { label: "Abogados activos", value: kpis.active_lawyers, rule: "bg-rule-strong" },
    { label: "Actuaciones del mes", value: kpis.actions_this_month, rule: "bg-rule-strong" },
    { label: "Audiencias próximas", value: kpis.upcoming_hearings, rule: "bg-brass" },
    { label: "Actuaciones pendientes", value: kpis.pending_actions, rule: "bg-brass" },
    {
      label: "Vencimientos abiertos",
      value: kpis.open_deadlines,
      rule: kpis.open_deadlines > 0 ? "bg-wax" : "bg-rule-strong",
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Resumen"
        title="Dashboard"
        description={`Estado de la firma a ${formatWhen(dashboard.generated_at).toLowerCase()}. Las cifras vienen del panel interno; aquí no se calcula ninguna.`}
      />

      <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <Card
            key={card.label}
            className="relative overflow-hidden px-5 pb-4 pt-5 transition-shadow hover:shadow-lift"
          >
            <span aria-hidden="true" className={`absolute inset-x-0 top-0 h-[3px] ${card.rule}`} />
            <p className="font-display text-[2.5rem] leading-none tracking-[-0.02em] text-ink">
              {card.value}
            </p>
            <p className="label-rule mt-2.5">{card.label}</p>
          </Card>
        ))}
      </div>

      <div className="mt-10 grid items-start gap-5 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="font-display text-xl">Expedientes recientes</h2>
          {dashboard.cases.length === 0 ? (
            <div className="mt-4">
              <EmptyState title="Sin expedientes" hint="No hay expedientes visibles para su perfil." />
            </div>
          ) : (
            <ul className="mt-4 divide-y divide-rule border-y border-rule">
              {dashboard.cases.map((item) => (
                <li key={item.id} className="flex items-center gap-4 py-3.5">
                  <span className="row-meta w-32 shrink-0">
                    {item.case_number}
                  </span>
                  <span className="min-w-0 flex-1">
                    <Link
                      href={`/admin/expedientes/${item.id}`}
                      className="row-title block truncate underline-offset-4 hover:underline"
                    >
                      {item.title}
                    </Link>
                    <span className="mt-0.5 block truncate text-xs text-ink-muted">
                      {item.client_name}
                    </span>
                  </span>
                  <span className="row-meta shrink-0">
                    {formatDate(item.opened_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-6">
          <h2 className="font-display text-xl">Vencimientos</h2>
          {dashboard.deadlines.length === 0 ? (
            <div className="mt-4">
              <EmptyState title="Sin vencimientos" hint="Nada vence en los próximos treinta días." />
            </div>
          ) : (
            <ul className="mt-4 divide-y divide-rule border-y border-rule">
              {dashboard.deadlines.map((item) => (
                <li key={`${item.source}-${item.reference_id}`} className="py-3.5">
                  <div className="flex items-center gap-3">
                    <span className="min-w-0 flex-1 truncate text-sm text-ink">
                      {item.title}
                    </span>
                    {item.is_overdue ? (
                      <Chip tone="wax" dot>
                        Vencido
                      </Chip>
                    ) : (
                      <Chip tone="brass" dot>
                        Pendiente
                      </Chip>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-ink-muted">
                    Vence {formatWhen(item.due_at).toLowerCase()}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <RuleNote>
        Panel generado el {formatWhen(dashboard.generated_at).toLowerCase()} para
        la vista «{dashboard.view}». Ninguna cifra de esta pantalla se calcula aquí.
      </RuleNote>
    </div>
  );
}