import Link from "next/link";
import { redirect } from "next/navigation";

import {
  EventForm,
  HearingForm,
  HearingUpdateButton,
  RescheduleHearingButton,
} from "@/components/admin/agenda/agenda-forms";
import { Button } from "@/components/admin/form-controls";
import { FilterBar, PageHeader } from "@/components/admin/page-furniture";
import { Card, Chip, EmptyState, RuleNote, SectionHeading } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import {
  createEvent,
  createHearing,
  rescheduleHearing,
  updateEvent,
  updateHearing,
} from "@/features/agenda/actions";
import { ApiNotAuthenticated, apiFetch } from "@/lib/api";
import {
  formatDate,
  formatTime,
  FIRM_TIME_ZONE,
  humanise,
  proceduralStageLabel,
  type Tone,
  visibilityLabel,
} from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type {
  CalendarEventRecord,
  CalendarEventType,
  CalendarView,
  CalendarViewResponse,
  CaseOption,
  DeadlineRecord,
  HearingRecord,
  PaginatedCases,
  PaginatedLawyers,
} from "@/lib/types";

const EVENT_TYPES: Array<{ value: CalendarEventType; label: string }> = [
  { value: "audiencia", label: "Audiencia" },
  { value: "reunion", label: "Reunión" },
  { value: "vencimiento", label: "Vencimiento" },
  { value: "llamada", label: "Llamada" },
  { value: "cita", label: "Cita" },
  { value: "recordatorio", label: "Recordatorio" },
];

export default async function AgendaPage({
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
  const view = calendarView(first(params.view));
  const reference = validDate(first(params.reference)) ?? today();
  const caseId = first(params.case_id);
  const lawyerId = first(params.lawyer_id);
  const eventType = first(params.event_type);

  const [calendarResult, hearingsResult, deadlinesResult, casesResult, lawyersResult] =
    await Promise.all([
      safely<CalendarViewResponse>("/api/v1/calendar", {
        view,
        reference,
        case_id: caseId,
        lawyer_id: lawyerId,
        event_type: eventType,
        limit: 500,
      }),
      safely<HearingRecord[]>("/api/v1/hearings", { limit: 500 }),
      safely<DeadlineRecord[]>("/api/v1/calendar/deadlines", { days: 90, limit: 100 }),
      safely<PaginatedCases>("/api/v1/cases", { skip: 0, limit: 200, open_only: true }),
      safely<PaginatedLawyers>("/api/v1/lawyers", {
        skip: 0,
        limit: 200,
        status: "activo",
      }),
    ]);

  const calendar = calendarResult.value;
  const events = calendar?.events ?? [];
  const hearings = hearingsResult.value ?? [];
  const deadlines = deadlinesResult.value ?? [];
  const hearingByEvent = new Map(hearings.map((hearing) => [hearing.event_id, hearing]));
  const caseOptions: CaseOption[] = (casesResult.value?.items ?? []).map((record) => ({
    id: record.id,
    label: `${record.case_number} · ${record.title}`,
  }));
  const lawyerOptions: CaseOption[] = (lawyersResult.value?.items ?? []).map((record) => ({
    id: record.id,
    label: record.full_name,
  }));
  const failed = calendarResult.failed || hearingsResult.failed || deadlinesResult.failed;
  const grouped = groupEvents(events);
  const permissions = session.profile.permissions;
  const canCreateEvent = permissions.includes("calendar:create");
  const canUpdateEvent = permissions.includes("calendar:update");
  const canCreateHearing = permissions.includes("hearings:create");
  const canUpdateHearing = permissions.includes("hearings:update");
  const canReschedule = permissions.includes("hearings:reschedule");

  const queryFor = (changes: Record<string, string | undefined>) => {
    const query = new URLSearchParams();
    query.set("view", changes.view ?? view);
    query.set("reference", changes.reference ?? reference);
    const filters = {
      case_id: changes.case_id ?? caseId,
      lawyer_id: changes.lawyer_id ?? lawyerId,
      event_type: changes.event_type ?? eventType,
    };
    for (const [key, value] of Object.entries(filters)) if (value) query.set(key, value);
    return `/admin/agenda?${query.toString()}`;
  };

  const previous = shiftReference(reference, view, -1);
  const next = shiftReference(reference, view, 1);

  return (
    <div>
      <PageHeader
        eyebrow="Operación"
        title="Agenda y audiencias"
        description="Señalamientos, reuniones y vencimientos de la firma. Las audiencias conservan sus reglas procesales y su traza de reprogramación."
        actions={
          <div className="flex flex-wrap justify-end gap-2">
            {canCreateHearing ? (
              <HearingForm action={createHearing} cases={caseOptions} lawyers={lawyerOptions} />
            ) : null}
            {canCreateEvent ? (
              <EventForm action={createEvent} cases={caseOptions} lawyers={lawyerOptions} />
            ) : null}
          </div>
        }
      />

      <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
        <nav aria-label="Vista de agenda" className="flex rounded-card border border-rule-strong bg-surface p-1 shadow-card">
          {(["day", "week", "month"] as CalendarView[]).map((item) => (
            <Link
              key={item}
              href={queryFor({ view: item })}
              aria-current={view === item ? "page" : undefined}
              className={`rounded-sm px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] transition-colors ${view === item ? "bg-ink text-paper" : "text-ink-muted hover:bg-surface-sunk hover:text-ink"}`}
            >
              {item === "day" ? "Día" : item === "week" ? "Semana" : "Mes"}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <Link href={queryFor({ reference: previous })} className="agenda-nav-button" aria-label="Periodo anterior">←</Link>
          <Link href={queryFor({ reference: today() })} className="agenda-nav-today">Hoy</Link>
          <Link href={queryFor({ reference: next })} className="agenda-nav-button" aria-label="Periodo siguiente">→</Link>
        </div>
      </div>

      <FilterBar>
        <input type="hidden" name="view" value={view} />
        <div>
          <label htmlFor="filtro-reference" className="label-rule block">Fecha de referencia</label>
          <input id="filtro-reference" name="reference" type="date" defaultValue={reference} className={SELECT} />
        </div>
        <div className="min-w-[13rem] flex-1">
          <label htmlFor="filtro-case_id" className="label-rule block">Expediente</label>
          <select id="filtro-case_id" name="case_id" defaultValue={caseId ?? ""} className={`${SELECT} w-full`}>
            <option value="">Todos</option>
            {caseOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="filtro-lawyer_id" className="label-rule block">Abogado</label>
          <select id="filtro-lawyer_id" name="lawyer_id" defaultValue={lawyerId ?? ""} className={SELECT}>
            <option value="">Todos</option>
            {lawyerOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="filtro-event_type" className="label-rule block">Tipo</label>
          <select id="filtro-event_type" name="event_type" defaultValue={eventType ?? ""} className={SELECT}>
            <option value="">Todos</option>
            {EVENT_TYPES.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </div>
        <Button type="submit" variant="secondary">Filtrar</Button>
        {caseId || lawyerId || eventType ? <Link href={`/admin/agenda?view=${view}&reference=${reference}`} className="pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted hover:text-wax">Limpiar</Link> : null}
      </FilterBar>

      {failed ? (
        <p className="mt-5 rounded-card border border-brass/40 bg-brass-tint px-4 py-3 text-sm text-brass">
          Una parte de la agenda no pudo cargarse. Los bloques disponibles se muestran sin disfrazar el fallo como una lista vacía.
        </p>
      ) : null}

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <Metric label="En el periodo" value={calendar?.total ?? 0} note={periodLabel(view, calendar?.start, calendar?.end)} />
        <Metric label="Audiencias" value={events.filter((event) => event.event_type === "audiencia").length} note="Con ficha procesal" />
        <Metric label="Vencidos" value={deadlines.filter((item) => item.overdue).length} note={`de ${deadlines.length} vencimientos próximos`} urgent={deadlines.some((item) => item.overdue)} />
      </div>

      <div className="mt-8 grid items-start gap-7 xl:grid-cols-[minmax(0,1fr)_21rem]">
        <section>
          <SectionHeading eyebrow="Cronología" title={periodTitle(view, reference)} />
          <div className="mt-4 space-y-5">
            {events.length === 0 ? (
              <EmptyState title="No hay eventos en este periodo" hint="Cambie la fecha, amplíe la vista o añada el primer evento." />
            ) : (
              grouped.map(([date, dateEvents]) => (
                <Card key={date} className="overflow-hidden">
                  <div className="border-b border-rule bg-surface-sunk px-5 py-3">
                    <p className="label-rule">{dateHeading(dateEvents[0]?.starts_at)}</p>
                  </div>
                  <ol className="divide-y divide-rule">
                    {dateEvents.map((event) => {
                      const hearing = hearingByEvent.get(event.id);
                      return (
                        <li key={event.id} className="agenda-entry grid gap-4 px-5 py-4 md:grid-cols-[5.25rem_minmax(0,1fr)_auto] md:items-center">
                          <div>
                            <p className="tnum text-sm font-semibold text-ink">{event.all_day ? "Todo el día" : formatTime(event.starts_at)}</p>
                            {!event.all_day ? <p className="tnum mt-0.5 text-[0.6875rem] text-ink-faint">hasta {formatTime(event.ends_at)}</p> : null}
                          </div>
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <Chip tone={eventTone(event)} dot>{eventTypeLabel(event.event_type)}</Chip>
                              <Chip tone={statusTone(event.status)}>{humanise(event.status)}</Chip>
                            </div>
                            <h3 className="row-title mt-2">{event.title}</h3>
                            <p className="mt-1 text-xs leading-relaxed text-ink-muted">
                              <Link href={`/admin/expedientes/${event.case_id}`} className="font-semibold text-ink-soft underline-offset-4 hover:text-wax hover:underline">{event.case_number}</Link>
                              {event.lawyer_name ? ` · ${event.lawyer_name}` : " · Sin abogado"}
                              {event.location ? ` · ${event.location}` : ""}
                            </p>
                            {hearing ? <p className="mt-1 text-xs text-ink-faint">{proceduralStageLabel(hearing.procedural_stage)}{hearing.court ? ` · ${hearing.court}` : ""}{hearing.courtroom ? ` · ${hearing.courtroom}` : ""}</p> : <p className="mt-1 text-xs text-ink-faint">{visibilityLabel(event.visibility)}</p>}
                          </div>
                          <div className="row-actions md:justify-self-end">
                            {hearing ? (
                              <>
                                {canUpdateHearing ? <HearingUpdateButton action={updateHearing} hearing={hearing} /> : null}
                                {canReschedule && !["realizada", "cancelada"].includes(hearing.status) ? <RescheduleHearingButton action={rescheduleHearing} hearing={hearing} /> : null}
                              </>
                            ) : canUpdateEvent ? (
                              <EventForm action={updateEvent} cases={caseOptions} lawyers={lawyerOptions} event={event} variant="quiet" />
                            ) : null}
                          </div>
                        </li>
                      );
                    })}
                  </ol>
                </Card>
              ))
            )}
          </div>
        </section>

        <aside>
          <SectionHeading eyebrow="Plazos" title="Vencimientos" />
          <Card className="mt-4 overflow-hidden">
            {deadlines.length === 0 ? (
              <div className="p-5 text-sm text-ink-muted">No hay vencimientos en los próximos 90 días.</div>
            ) : (
              <ol className="divide-y divide-rule">
                {deadlines.slice(0, 12).map((item) => (
                  <li key={`${item.source}-${item.reference_id}`} className="px-4 py-3.5">
                    <div className="flex items-start justify-between gap-3">
                      <Chip tone={item.overdue ? "wax" : "brass"} dot>{item.overdue ? "Vencido" : item.source_label}</Chip>
                      <time className="row-meta">{formatDate(item.due_at)}</time>
                    </div>
                    <p className="mt-2 text-sm font-medium leading-snug text-ink">{item.title}</p>
                    <Link href={`/admin/expedientes/${item.case_id}`} className="row-meta mt-1.5 inline-block hover:text-wax">{item.case_number}</Link>
                  </li>
                ))}
              </ol>
            )}
          </Card>
          <RuleNote>Los vencimientos incluyen eventos explícitos y próximas actuaciones. Lo vencido no desaparece del cálculo.</RuleNote>
        </aside>
      </div>
    </div>
  );
}

function Metric({ label, value, note, urgent = false }: { label: string; value: number; note: string; urgent?: boolean }) {
  return (
    <Card className={`px-5 py-4 ${urgent ? "border-wax/35 bg-wax-tint" : ""}`}>
      <p className="label-rule">{label}</p>
      <div className="mt-2 flex items-end justify-between gap-4"><p className={`font-display text-4xl ${urgent ? "text-wax-deep" : "text-ink"}`}>{value}</p><p className="max-w-[11rem] text-right text-xs leading-relaxed text-ink-muted">{note}</p></div>
    </Card>
  );
}

const SELECT = "mt-1.5 rounded-card border border-rule-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-wax";

function first(value: string | string[] | undefined): string | undefined { return Array.isArray(value) ? value[0] : value; }
function today(): string { return new Date().toISOString().slice(0, 10); }
function validDate(value?: string): string | undefined { return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : undefined; }
function calendarView(value?: string): CalendarView { return value === "day" || value === "month" ? value : "week"; }

function shiftReference(reference: string, view: CalendarView, direction: number): string {
  const value = new Date(`${reference}T12:00:00Z`);
  if (view === "month") value.setUTCMonth(value.getUTCMonth() + direction);
  else value.setUTCDate(value.getUTCDate() + direction * (view === "week" ? 7 : 1));
  return value.toISOString().slice(0, 10);
}

function groupEvents(events: CalendarEventRecord[]): Array<[string, CalendarEventRecord[]]> {
  const groups = new Map<string, CalendarEventRecord[]>();
  for (const event of events) {
    const key = event.starts_at.slice(0, 10);
    groups.set(key, [...(groups.get(key) ?? []), event]);
  }
  return [...groups.entries()];
}

function eventTypeLabel(value: string): string { return EVENT_TYPES.find((item) => item.value === value)?.label ?? humanise(value); }
function eventTone(event: CalendarEventRecord): Tone { if (event.event_type === "vencimiento") return "wax"; if (event.event_type === "audiencia") return "brass"; return "neutral"; }
function statusTone(value: string): Tone { if (value === "realizada") return "forest"; if (value === "cancelada") return "ink"; if (value === "aplazada") return "brass"; return "neutral"; }
function dateHeading(iso?: string): string { if (!iso) return "Fecha"; return new Intl.DateTimeFormat("es-ES", { weekday: "long", day: "2-digit", month: "long", year: "numeric", timeZone: FIRM_TIME_ZONE }).format(new Date(iso)); }
function periodTitle(view: CalendarView, reference: string): string { const date = new Date(`${reference}T12:00:00Z`); if (view === "day") return formatDate(date.toISOString()); if (view === "month") return new Intl.DateTimeFormat("es-ES", { month: "long", year: "numeric", timeZone: FIRM_TIME_ZONE }).format(date); return `Semana de ${formatDate(date.toISOString())}`; }
function periodLabel(view: CalendarView, start?: string, end?: string): string {
  if (!start || !end) return humanise(view);
  const inclusiveEnd = new Date(new Date(end).getTime() - 1);
  return `${formatDate(start)} — ${formatDate(inclusiveEnd.toISOString())}`;
}

async function safely<T>(path: string, query: Record<string, string | number | boolean | undefined>): Promise<{ value: T | null; failed: boolean }> {
  try { return { value: await apiFetch<T>(path, { query }), failed: false }; }
  catch (error) { if (error instanceof ApiNotAuthenticated) redirect("/login"); return { value: null, failed: true }; }
}
