import Link from "next/link";
import { redirect } from "next/navigation";

import { Masthead } from "@/components/masthead";
import {
  Card,
  Chip,
  EmptyState,
  Field,
  RuleNote,
  SectionHeading,
} from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import {
  caseStatusTone,
  clientRequestStatusLabel,
  clientRequestTypeLabel,
  documentStatusLabel,
  documentStatusTone,
  documentTypeLabel,
  evidenceStatusLabel,
  evidenceStatusTone,
  formatDate,
  formatWhen,
  proceduralStageLabel,
  relativeMoment,
} from "@/lib/format";
import { loadForSession, requireSession } from "@/lib/session-guard";
import type { ClientRequestRecord, DashboardPayload } from "@/lib/types";

/**
 * The client panel.
 *
 * Everything on this page is already scoped by the backend. The panel does not
 * filter, and it does not decide what a client may see — it renders what the
 * API decided that caller is allowed to see.
 */
export default async function PortalPage() {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} backHref="/login" backLabel="Ir al acceso" />;
  }
  const profile = session.profile;

  const [dashboardResult, requestsResult] = await Promise.all([
    loadForSession<DashboardPayload>("/api/v1/dashboard"),
    loadForSession<ClientRequestRecord[]>("/api/v1/client-requests"),
  ]);
  const dashboard = dashboardResult.value;
  const failed = dashboardResult.failed;
  if (failed || !dashboard) {
    return <ServiceUnavailable backHref="/login" backLabel="Ir al acceso" />;
  }
  const clientRequests = (requestsResult.value ?? []).filter((r) => r.status === "pendiente" || r.status === "respondida");
  const pendingRequests = clientRequests.filter((r) => r.status === "pendiente");

  const { kpis, cases, next_hearing: nextHearing, deadlines, documents, evidences } =
    dashboard;
  const firstName = profile.name.split(" ")[0];
  const overdue = deadlines.filter((item) => item.is_overdue);
  const attentionItems = [
    ...(pendingRequests.length > 0
      ? [
          {
            key: "requests",
            href: pendingRequests[0] ? `/portal/casos/${pendingRequests[0].case_id}` : "/portal",
            title:
              pendingRequests.length === 1
                ? "Tiene 1 solicitud pendiente del despacho"
                : `Tiene ${pendingRequests.length} solicitudes pendientes del despacho`,
            detail: "Revise y responda documentos, información o tareas solicitadas.",
            tone: "brass" as const,
          },
        ]
      : []),
    ...(kpis.pending_messages > 0
      ? [
          {
            key: "messages",
            href: "/portal/mensajes",
            title:
              kpis.pending_messages === 1
                ? "Tiene 1 mensaje pendiente"
                : `Tiene ${kpis.pending_messages} mensajes pendientes`,
            detail: "Revise la bandeja para responder o confirmar información.",
            tone: "forest" as const,
          },
        ]
      : []),
    ...(kpis.overdue_deadlines > 0
      ? [
          {
            key: "overdue",
            href: "/portal",
            title:
              kpis.overdue_deadlines === 1
                ? "Hay 1 plazo vencido"
                : `Hay ${kpis.overdue_deadlines} plazos vencidos`,
            detail: "Consulte los vencimientos y contacte al despacho si necesita orientación.",
            tone: "wax" as const,
          },
        ]
      : []),
    ...(kpis.unread_notifications > 0
      ? [
          {
            key: "notifications",
            href: "/portal",
            title:
              kpis.unread_notifications === 1
                ? "Tiene 1 notificación nueva"
                : `Tiene ${kpis.unread_notifications} notificaciones nuevas`,
            detail: "Hay novedades relacionadas con sus expedientes.",
            tone: "brass" as const,
          },
        ]
      : []),
  ];

  return (
    <Masthead
      eyebrow="WABOGADOS"
      title="Portal del cliente"
      profile={{ name: profile.name, role: profile.roleLabel, unread: profile.unread }}
      nav={[
        { href: "/portal", label: "Mi expediente", active: true },
        { href: "/portal/mensajes", label: "Mensajes" },
        { href: "/portal/documentos", label: "Documentos" },
      ]}
    >
      <section className="rise">
        <p className="label-rule">
          {new Intl.DateTimeFormat("es-ES", {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric",
          }).format(new Date())}
        </p>
        <h1 className="font-display mt-2 text-[2.5rem] leading-[1.08] sm:text-5xl">
          Buenos días, {firstName}.
        </h1>
        <p className="mt-3 max-w-2xl text-[0.95rem] leading-relaxed text-ink-soft">
          {nextHearing
            ? `Su próxima audiencia es ${relativeMoment(nextHearing.starts_at) ?? formatDate(nextHearing.starts_at)}.`
            : "No tiene audiencias programadas en este momento."}
          {kpis.open_deadlines > 0
            ? ` Tiene ${kpis.open_deadlines} ${kpis.open_deadlines === 1 ? "plazo abierto" : "plazos abiertos"}.`
            : ""}
        </p>
      </section>

      <section
        aria-label="Resumen"
        className="mt-9 grid gap-px overflow-hidden rounded-card border border-rule bg-rule sm:grid-cols-2 xl:grid-cols-4"
      >
        <Stat index={0} value={cases.length} label="Procesos activos" tone="ink" />
        <Stat
          index={1}
          value={kpis.upcoming_hearings}
          label="Audiencias previstas"
          tone="forest"
        />
        <Stat index={2} value={kpis.open_deadlines} label="Plazos abiertos" tone="brass" />
        <Stat
          index={3}
          value={kpis.pending_messages}
          label="Mensajes pendientes"
          tone={kpis.pending_messages > 0 ? "wax" : "ink"}
          href="/portal/mensajes"
        />
      </section>

      {attentionItems.length > 0 ? (
        <section className="rise mt-10" style={{ animationDelay: "50ms" }}>
          <SectionHeading eyebrow="Acción" title="Requiere su atención" />
          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {attentionItems.map((item) => (
              <Link key={item.key} href={item.href} className="group block">
                <Card className="h-full p-5 transition-all duration-200 group-hover:-translate-y-px group-hover:border-rule-strong">
                  <Chip tone={item.tone} dot>
                    Atención
                  </Chip>
                  <p className="mt-3 font-display text-xl leading-snug text-ink">{item.title}</p>
                  <p className="mt-2 text-sm text-ink-muted">{item.detail}</p>
                </Card>
              </Link>
            ))}
          </div>
        </section>
      ) : null}


      {clientRequests.length > 0 ? (
        <section className="rise mt-10" style={{ animationDelay: "70ms" }}>
          <SectionHeading eyebrow="Despacho" title="Solicitudes y tareas" />
          <Card className="mt-5 overflow-hidden">
            <ul className="divide-y divide-rule">
              {clientRequests.slice(0, 5).map((item) => (
                <li key={item.id} className="px-5 py-4">
                  <Link href={`/portal/casos/${item.case_id}`} className="group block">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-ink group-hover:text-forest">{item.title}</p>
                        <p className="mt-0.5 text-xs text-ink-muted">
                          {item.case_number ?? "Expediente"} · {clientRequestTypeLabel(item.request_type)}
                          {item.due_at ? ` · vence ${formatDate(item.due_at)}` : ""}
                          {item.is_overdue ? " · vencida" : ""}
                        </p>
                      </div>
                      <Chip tone={item.status === "pendiente" ? (item.is_overdue ? "wax" : "brass") : "forest"} dot>
                        {clientRequestStatusLabel(item.status)}
                      </Chip>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      ) : null}

      <div className="mt-12 grid gap-10 lg:grid-cols-[1.35fr_1fr]">
        <div className="space-y-10">
          <section className="rise" style={{ animationDelay: "80ms" }}>
            <SectionHeading
              eyebrow="Situación"
              title="Mis procesos"
              action={
                cases.length > 0 ? (
                  <span className="text-xs text-ink-muted">Seleccione un proceso para ver su avance</span>
                ) : undefined
              }
            />
            {cases.length === 0 ? (
              <div className="mt-5">
                <EmptyState
                  title="Todavía no tiene procesos"
                  hint="Cuando el despacho abra un expediente a su nombre aparecerá aquí."
                />
              </div>
            ) : (
              <ul className="mt-5 space-y-3">
                {cases.map((item) => (
                  <li key={item.id}>
                    <CaseRow id={item.id} item={item} />
                  </li>
                ))}
              </ul>
            )}
          </section>

          {documents.length > 0 ? (
            <section className="rise" style={{ animationDelay: "140ms" }}>
              <SectionHeading
                eyebrow="A su disposición"
                title="Documentos publicados"
                action={
                  <Link href="/portal/documentos" className="text-xs text-forest underline-offset-4 hover:underline">
                    Ver todos
                  </Link>
                }
              />
              <Card className="mt-5 overflow-hidden">
                <ul className="divide-y divide-rule">
                  {documents.slice(0, 6).map((document) => (
                    <li
                      key={document.id}
                      className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-5 py-3.5"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">{document.title}</p>
                        <p className="text-xs text-ink-muted">
                          {documentTypeLabel(document.document_type)} · {formatDate(document.created_at)}
                        </p>
                      </div>
                      <Chip tone={documentStatusTone(document.status)} dot>
                        {documentStatusLabel(document.status)}
                      </Chip>
                    </li>
                  ))}
                </ul>
              </Card>
              <RuleNote>
                Los documentos publicados se muestran para su conocimiento. Los originales los conserva el despacho; la descarga puede requerir autorización según la política del expediente.
              </RuleNote>
            </section>
          ) : null}
        </div>

        <div className="space-y-10">
          <section className="rise" style={{ animationDelay: "200ms" }}>
            <SectionHeading eyebrow="Agenda" title="Próxima audiencia" />
            <Card className="mt-5 p-5">
              {nextHearing ? (
                <>
                  <p className="font-display text-2xl leading-tight">{nextHearing.title}</p>
                  <p className="mt-2 text-sm text-forest">{formatWhen(nextHearing.starts_at)}</p>
                  <dl className="mt-5 grid grid-cols-2 gap-4">
                    <Field label="Sala">{nextHearing.courtroom ?? nextHearing.court ?? "—"}</Field>
                    <Field label="Juzgado">{nextHearing.court ?? "—"}</Field>
                    <Field label="Trámite" className="col-span-2">
                      {proceduralStageLabel(nextHearing.procedural_stage)}
                    </Field>
                  </dl>
                </>
              ) : (
                <p className="text-sm text-ink-muted">
                  Sin audiencias programadas. El despacho le avisará en cuanto se fije una.
                </p>
              )}
            </Card>
          </section>

          <section className="rise" style={{ animationDelay: "260ms" }}>
            <SectionHeading eyebrow="Plazos" title="Próximos vencimientos" />
            <Card className="mt-5 p-5">
              {deadlines.length === 0 ? (
                <p className="text-sm text-ink-muted">No hay plazos registrados por ahora.</p>
              ) : (
                <ul className="space-y-3.5">
                  {deadlines.slice(0, 6).map((item) => (
                    <li key={`${item.source}-${item.reference_id}`} className="flex gap-3">
                      <span
                        aria-hidden="true"
                        className={`mt-1.5 size-2 shrink-0 rounded-full ${
                          item.is_overdue ? "bg-wax" : "bg-forest"
                        }`}
                      />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-ink">{item.title}</p>
                        <p className="text-xs text-ink-muted">
                          {formatDate(item.due_at)}
                          {item.is_overdue ? " · vencido" : ""}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              {overdue.length > 0 ? (
                <p className="mt-4 border-t border-rule pt-4 text-xs text-wax-deep">
                  Revise los plazos vencidos con su abogado o asistente asignado.
                </p>
              ) : null}
            </Card>
          </section>

          {evidences.length > 0 ? (
            <section className="rise" style={{ animationDelay: "320ms" }}>
              <SectionHeading eyebrow="Prueba" title="Evidencias visibles" />
              <Card className="mt-5 p-5">
                <ul className="space-y-4">
                  {evidences.slice(0, 5).map((item) => (
                    <li key={item.id} className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-ink">{item.title}</p>
                        <p className="text-xs text-ink-muted">{formatDate(item.created_at)}</p>
                      </div>
                      <Chip tone={evidenceStatusTone(item.status)}>
                        {evidenceStatusLabel(item.status)}
                      </Chip>
                    </li>
                  ))}
                </ul>
                <p className="mt-5 border-t border-rule pt-4 text-xs leading-relaxed text-ink-faint">
                  Las evidencias se muestran en la versión preparada para su consulta. Los originales los conserva el despacho.
                </p>
              </Card>
            </section>
          ) : null}
        </div>
      </div>
    </Masthead>
  );
}

function CaseRow({
  id,
  item,
}: {
  id: string;
  item: DashboardPayload["cases"][number];
}) {
  return (
    <Link
      href={`/portal/casos/${id}`}
      className="group block rounded-card border border-rule bg-surface px-5 py-4 transition-all duration-200 hover:-translate-y-px hover:border-rule-strong hover:shadow-[0_6px_18px_-10px_rgba(25,27,24,0.4)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="tnum text-xs text-ink-muted">{item.case_number}</p>
          <p className="font-display mt-0.5 text-xl leading-snug text-ink">{item.title}</p>
        </div>
        <Chip tone={caseStatusTone(item.status)}>{item.status}</Chip>
      </div>
      <div className="mt-3 flex items-center justify-between gap-3 text-xs text-ink-faint">
        <span>Abierto el {formatDate(item.opened_at)}</span>
        <span className="text-forest group-hover:underline underline-offset-4">Ver avance</span>
      </div>
    </Link>
  );
}

function Stat({
  value,
  label,
  tone,
  index,
  href,
}: {
  value: number;
  label: string;
  tone: "ink" | "forest" | "brass" | "wax";
  index: number;
  href?: string;
}) {
  const toneClass = {
    ink: "text-ink",
    forest: "text-forest",
    brass: "text-brass",
    wax: "text-wax",
  }[tone];

  const body = (
    <div className="rise bg-surface px-5 py-6" style={{ animationDelay: `${index * 60}ms` }}>
      <p className={`font-display text-4xl leading-none ${toneClass}`}>{value}</p>
      <p className="label-rule mt-2">{label}</p>
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="block transition-colors hover:bg-paper">
        {body}
      </Link>
    );
  }
  return body;
}
