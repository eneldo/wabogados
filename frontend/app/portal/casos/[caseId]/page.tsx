import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { Masthead } from "@/components/masthead";
import {
  Card,
  Chip,
  EmptyState,
  Field,
  Label,
  SectionHeading,
} from "@/components/primitives";
import { ClientRequestRespondForm } from "@/components/portal/client-request-respond";
import { ServiceUnavailable } from "@/components/service-unavailable";
import {
  actionTypeLabel,
  caseStatusTone,
  clientRequestStatusLabel,
  clientRequestStatusTone,
  clientRequestTypeLabel,
  milestoneStatusLabel,
  milestoneStatusTone,
  evidenceStatusLabel,
  evidenceStatusTone,
  formatDate,
  formatDateTime,
  formatWhen,
  proceduralStageLabel,
  visibilityLabel,
  visibilityTone,
} from "@/lib/format";
import { loadForSession, requireSession } from "@/lib/session-guard";
import type {
  CaseMilestoneRecord,
  CaseTimelineResponse,
  ClientRequestRecord,
  DashboardHearing,
  Evidence,
} from "@/lib/types";

/**
 * One file, seen whole.
 *
 * A client asking "how is my case going" wants the file, not a menu: published
 * activity, what stage it is in, what the court has set, and what documents or
 * evidences have been shared. Everything here comes from scoped endpoints, so a
 * client outside the file never reaches this page at all — the API answers 404
 * and so does this one.
 */
export default async function CaseDetailPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;

  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} />;
  }
  const profile = session.profile;

  const [{ value: evidences, failed: evidencesFailed }, timelineResult, requestsResult, milestonesResult, dashboardResult] =
    await Promise.all([
      loadForSession<Evidence[]>(`/api/v1/cases/${caseId}/evidences`),
      loadForSession<CaseTimelineResponse>(`/api/v1/cases/${caseId}/timeline`, {
        query: { limit: 100 },
      }),
      loadForSession<ClientRequestRecord[]>(`/api/v1/cases/${caseId}/client-requests`),
      loadForSession<CaseMilestoneRecord[]>(`/api/v1/cases/${caseId}/milestones`),
      loadForSession<{
        cases: Array<{
          id: string;
          case_number: string;
          title: string;
          status: string;
          client_name: string;
          opened_at: string;
        }>;
        hearings: DashboardHearing[];
        deadlines: Array<{
          source: string;
          reference_id: string;
          case_id: string;
          title: string;
          due_at: string;
          is_overdue: boolean;
        }>;
      }>("/api/v1/dashboard", { query: { limit: 50 } }),
    ]);

  if (evidencesFailed) return <ServiceUnavailable />;
  const timeline = timelineResult.value;
  const timelineFailed = timelineResult.failed;
  const requests = requestsResult.value ?? [];
  const milestones = milestonesResult.value ?? [];
  const dashboard = dashboardResult.value;

  // The dashboard carries the case header fields, so a case outside the caller's
  // scope never appears in it and this page reports 404 rather than an empty file.
  const summary = dashboard?.cases.find((item) => item.id === caseId);
  if (!summary) notFound();

  const hearings = (dashboard?.hearings ?? []).filter(
    (item) => item.case_id === caseId,
  );
  const deadlines = (dashboard?.deadlines ?? []).filter(
    (item) => item.case_id === caseId,
  );
  const lastUpdate = timeline?.entries[0]?.action.occurred_at ?? summary.opened_at;

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
      <nav aria-label="Ruta" className="mb-6 text-xs text-ink-muted">
        <Link href="/portal" className="underline-offset-4 hover:underline">
          Mi expediente
        </Link>
        <span aria-hidden="true" className="px-2">
          /
        </span>
        <span className="tnum">{summary.case_number}</span>
      </nav>

      <header className="rise">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <Label>{summary.case_number}</Label>
            <h1 className="font-display mt-1.5 text-[2.25rem] leading-[1.1]">
              {summary.title}
            </h1>
            <p className="mt-2 text-sm text-ink-muted">
              {summary.client_name} · abierto el {formatDate(summary.opened_at)}
            </p>
            <p className="mt-1 text-xs text-ink-faint">
              Última actualización publicada: {formatDateTime(lastUpdate)}
            </p>
          </div>
          <Chip tone={caseStatusTone(summary.status)}>
            {summary.status === "abierto" ? "En curso" : summary.status}
          </Chip>
        </div>
      </header>

      <div className="mt-10 grid gap-10 lg:grid-cols-[1.35fr_1fr]">
        <div className="space-y-10">


          <section className="rise" style={{ animationDelay: "10ms" }}>
            <SectionHeading eyebrow="Progreso" title="Etapas del caso" />
            {milestones.length === 0 ? (
              <Card className="mt-5 p-5">
                <p className="text-sm text-ink-muted">
                  El despacho publicará las etapas relevantes de este caso cuando estén disponibles.
                </p>
              </Card>
            ) : (
              <Card className="mt-5 overflow-hidden">
                <ol className="divide-y divide-rule">
                  {milestones.map((item, index) => (
                    <li key={item.id} className="px-5 py-4 sm:px-6">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-[0.6875rem] font-semibold uppercase tracking-[0.1em] text-ink-faint">
                              Etapa {index + 1}
                            </span>
                            <Chip tone={milestoneStatusTone(item.status)} dot>
                              {milestoneStatusLabel(item.status)}
                            </Chip>
                          </div>
                          <p className="mt-1.5 font-medium text-ink">{item.title}</p>
                          {item.description ? (
                            <p className="mt-1 text-sm text-ink-muted">{item.description}</p>
                          ) : null}
                        </div>
                        <div className="shrink-0 text-right text-xs text-ink-faint">
                          {item.completed_at ? <p>Completada: {formatDate(item.completed_at)}</p> : null}
                          {!item.completed_at && item.planned_at ? <p>Prevista: {formatDate(item.planned_at)}</p> : null}
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              </Card>
            )}
          </section>

          <section className="rise" style={{ animationDelay: "20ms" }}>
            <SectionHeading
              eyebrow="Pendientes"
              title="Solicitudes del despacho"
              action={
                requests.length > 0 ? (
                  <span className="text-xs text-ink-muted">
                    {requests.filter((r) => r.status === "pendiente").length} pendiente(s)
                  </span>
                ) : undefined
              }
            />
            {requests.length === 0 ? (
              <div className="mt-5">
                <EmptyState
                  title="Sin solicitudes pendientes"
                  hint="Cuando el despacho le solicite documentos, información o tareas aparecerán aquí."
                />
              </div>
            ) : (
              <Card className="mt-5 overflow-hidden">
                <ul className="divide-y divide-rule">
                  {requests.map((item) => (
                    <li key={item.id} className="px-5 py-5 sm:px-6">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <Chip tone={clientRequestStatusTone(item.status)} dot>
                              {clientRequestStatusLabel(item.status)}
                            </Chip>
                            <Chip tone="neutral" dot>{clientRequestTypeLabel(item.request_type)}</Chip>
                            {item.is_overdue ? <Chip tone="wax">Vencida</Chip> : null}
                          </div>
                          <p className="mt-2 font-medium text-ink">{item.title}</p>
                          {item.description ? (
                            <p className="mt-1 text-sm text-ink-muted">{item.description}</p>
                          ) : null}
                          {item.due_at ? (
                            <p className="mt-2 text-xs text-ink-faint">
                              Vence: {formatWhen(item.due_at)} · {formatDateTime(item.due_at)}
                            </p>
                          ) : null}
                          {item.response_text ? (
                            <div className="mt-3 rounded-md border border-rule bg-paper/60 px-3 py-2.5">
                              <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.1em] text-ink-faint">Su respuesta</p>
                              <p className="mt-1 text-sm text-ink">{item.response_text}</p>
                              {item.responded_at ? (
                                <p className="mt-1 text-xs text-ink-muted">Enviada: {formatDateTime(item.responded_at)}</p>
                              ) : null}
                            </div>
                          ) : null}
                          {item.status === "pendiente" ? <ClientRequestRespondForm requestId={item.id} /> : null}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </section>

          <section className="rise" style={{ animationDelay: "40ms" }}>
            <SectionHeading
              eyebrow="Avance"
              title="Actividad del caso"
              action={
                timeline && timeline.total > 0 ? (
                  <span className="text-xs text-ink-muted">
                    {timeline.total}{" "}
                    {timeline.total === 1 ? "actualización" : "actualizaciones"}
                  </span>
                ) : undefined
              }
            />
            {timelineFailed ? (
              <Card className="mt-5 p-5">
                <p className="text-sm text-ink-muted">
                  No fue posible cargar la actividad publicada en este momento.
                </p>
              </Card>
            ) : !timeline || timeline.entries.length === 0 ? (
              <div className="mt-5">
                <EmptyState
                  title="Sin actividad publicada"
                  hint="Cuando el despacho publique avances de este expediente aparecerán aquí en orden cronológico."
                />
              </div>
            ) : (
              <Card className="mt-5 overflow-hidden">
                <ol className="divide-y divide-rule">
                  {timeline.entries.map((entry, index) => (
                    <li key={entry.action.id} className="relative px-5 py-5 sm:px-6">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <Chip tone="forest" dot>
                              {actionTypeLabel(entry.action.action_type)}
                            </Chip>
                            {entry.is_pending ? (
                              <Chip tone="brass" dot>
                                Próximo paso pendiente
                              </Chip>
                            ) : null}
                          </div>
                          <p className="mt-2 text-sm leading-6 text-ink">
                            {entry.action.description}
                          </p>
                          {entry.action.result ? (
                            <p className="mt-2 text-sm text-ink-muted">
                              <span className="font-medium text-ink-soft">Resultado: </span>
                              {entry.action.result}
                            </p>
                          ) : null}
                          {entry.action.next_action ? (
                            <div className="mt-3 rounded-md border border-rule bg-paper/60 px-3 py-2.5">
                              <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.1em] text-ink-faint">
                                Próximo paso
                              </p>
                              <p className="mt-1 text-sm text-ink">{entry.action.next_action}</p>
                              {entry.action.next_action_at ? (
                                <p className="mt-0.5 text-xs text-ink-muted">
                                  {formatWhen(entry.action.next_action_at)} ·{" "}
                                  {formatDateTime(entry.action.next_action_at)}
                                </p>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                        <div className="shrink-0 text-right">
                          <p className="text-xs font-medium text-ink-soft">
                            {formatDate(entry.action.occurred_at)}
                          </p>
                          <p className="mt-0.5 text-[0.6875rem] text-ink-faint">
                            {formatDateTime(entry.action.occurred_at)}
                          </p>
                          {entry.action.responsible_lawyer_name ? (
                            <p className="mt-2 text-[0.6875rem] text-ink-muted">
                              {entry.action.responsible_lawyer_name}
                            </p>
                          ) : null}
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              </Card>
            )}
          </section>

          <section className="rise" style={{ animationDelay: "80ms" }}>
            <SectionHeading eyebrow="Prueba" title="Evidencias" />
            {(evidences ?? []).length === 0 ? (
              <div className="mt-5">
                <EmptyState
                  title="Sin evidencias publicadas"
                  hint="Cuando el despacho publique prueba documental en este expediente aparecerá aquí."
                />
              </div>
            ) : (
              <Card className="mt-5 overflow-hidden">
                <ul className="divide-y divide-rule">
                  {(evidences ?? []).map((item) => (
                    <li
                      key={item.id}
                      className="flex flex-wrap items-center justify-between gap-3 px-5 py-4"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">{item.title}</p>
                        <p className="text-xs text-ink-muted">
                          {formatDate(item.captured_at ?? item.created_at)}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <Chip tone={visibilityTone(item.visibility)}>
                          {visibilityLabel(item.visibility)}
                        </Chip>
                        <Chip tone={evidenceStatusTone(item.status)}>
                          {evidenceStatusLabel(item.status)}
                        </Chip>
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </section>
        </div>

        <div className="space-y-10">
          <section className="rise" style={{ animationDelay: "120ms" }}>
            <SectionHeading eyebrow="Agenda" title="Audiencias" />
            <Card className="mt-5 p-5">
              {hearings.length === 0 ? (
                <p className="text-sm text-ink-muted">
                  Sin audiencias programadas.
                </p>
              ) : (
                <ul className="space-y-5">
                  {hearings.map((item) => (
                    <li key={item.id} className="border-b border-rule pb-5 last:border-0 last:pb-0">
                      <p className="font-display text-lg leading-snug">{item.title}</p>
                      <p className="mt-1 text-sm text-forest">
                        {formatWhen(item.starts_at)}
                      </p>
                      <dl className="mt-3 grid grid-cols-2 gap-3">
                        <Field label="Sala">{item.courtroom ?? "—"}</Field>
                        <Field label="Trámite">
                          {proceduralStageLabel(item.procedural_stage)}
                        </Field>
                      </dl>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </section>

          {deadlines.length > 0 ? (
            <section className="rise" style={{ animationDelay: "160ms" }}>
              <SectionHeading eyebrow="Plazos" title="Pendiente de su parte" />
              <Card className="mt-5 p-5">
                <ul className="space-y-3.5">
                  {deadlines.map((item) => (
                    <li key={`${item.source}-${item.reference_id}`} className="flex gap-3">
                      <span
                        aria-hidden="true"
                        className={`mt-1.5 size-2 shrink-0 rounded-full ${
                          item.is_overdue ? "bg-wax" : "bg-forest"
                        }`}
                      />
                      <div>
                        <p className="text-sm font-medium text-ink">{item.title}</p>
                        <p className="text-xs text-ink-muted">
                          {formatDate(item.due_at)}
                          {item.is_overdue ? " · vencido" : ""}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          ) : null}
        </div>
      </div>
    </Masthead>
  );
}
