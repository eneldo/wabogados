import Link from "next/link";
import { redirect } from "next/navigation";

import { Masthead } from "@/components/masthead";
import {
  Card,
  Chip,
  EmptyState,
  Field,
  SectionHeading,
} from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import {
  caseStatusTone,
  evidenceStatusLabel,
  evidenceStatusTone,
  formatDate,
  formatWhen,
  proceduralStageLabel,
  relativeMoment,
} from "@/lib/format";
import { loadForSession, requireSession } from "@/lib/session-guard";
import type { DashboardPayload } from "@/lib/types";

/**
 * The client panel.
 *
 * Everything on this page is already scoped by the backend. The panel does not
 * filter, and it does not decide what a client may see — it renders what the
 * API decided that caller is allowed to see. That is the whole reason the
 * figures cannot disagree with the detail.
 */
export default async function PortalPage() {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} backHref="/login" backLabel="Ir al acceso" />;
  }
  const profile = session.profile;

  const { value: dashboard, failed } = await loadForSession<DashboardPayload>(
    "/api/v1/dashboard",
  );
  // A failed call is not a missing session, and it is not an empty dashboard.
  // Saying "you have no cases" when the API is down would be a lie the user
  // would act on.
  if (failed || !dashboard) {
    return (
      <ServiceUnavailable backHref="/login" backLabel="Ir al acceso" />
    );
  }

  const { kpis, cases, next_hearing: nextHearing, deadlines, documents, evidences } =
    dashboard;
  const firstName = profile.name.split(" ")[0];

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
      {/* Greeting. The date is the kind of detail that makes a portal feel
          attended to rather than generated. */}
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
        </p>
      </section>

      <section
        aria-label="Resumen"
        className="mt-9 grid gap-px overflow-hidden rounded-card border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-4"
      >
        <Stat index={0} value={cases.length} label="Procesos activos" tone="ink" />
        <Stat
          index={1}
          value={kpis.upcoming_hearings}
          label="Audiencias previstas"
          tone="forest"
        />
        <Stat
          index={2}
          value={documents.length}
          label="Documentos publicados"
          tone="brass"
        />
        <Stat
          index={3}
          value={evidences.length}
          label="Evidencias a su disposición"
          tone="wax"
        />
      </section>

      <div className="mt-12 grid gap-10 lg:grid-cols-[1.35fr_1fr]">
        <div className="space-y-10">
          {/* --- Processes ------------------------------------------------ */}
          <section className="rise" style={{ animationDelay: "80ms" }}>
            <SectionHeading eyebrow="Situación" title="Mis procesos" />
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

          {/* --- Published documents ------------------------------------- */}
          {documents.length > 0 ? (
            <section className="rise" style={{ animationDelay: "140ms" }}>
              <SectionHeading eyebrow="A su disposición" title="Documentos publicados" />
              <Card className="mt-5 overflow-hidden">
                <ul className="divide-y divide-rule">
                  {documents.map((document) => (
                    <li
                      key={document.id}
                      className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-5 py-3.5"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">{document.title}</p>
                        <p className="text-xs text-ink-muted">
                          {document.document_type} · {formatDate(document.created_at)}
                        </p>
                      </div>
                      <Chip tone="forest">Publicado</Chip>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          ) : null}
        </div>

        <div className="space-y-10">
          {/* --- Next hearing -------------------------------------------- */}
          <section className="rise" style={{ animationDelay: "200ms" }}>
            <SectionHeading eyebrow="Agenda" title="Próxima audiencia" />
            <Card className="mt-5 p-5">
              {nextHearing ? (
                <>
                  <p className="font-display text-2xl leading-tight">
                    {nextHearing.title}
                  </p>
                  <p className="mt-2 text-sm text-ink-soft">
                    {formatWhen(nextHearing.starts_at)}
                  </p>
                  <dl className="mt-5 grid grid-cols-2 gap-4">
                    <Field label="Sala">
                      {nextHearing.courtroom ?? nextHearing.court ?? "—"}
                    </Field>
                    <Field label="Juzgado">
                      {nextHearing.court ?? "—"}
                    </Field>
                    <Field label="Trámite" className="col-span-2">
                      {proceduralStageLabel(nextHearing.procedural_stage)}
                    </Field>
                  </dl>
                </>
              ) : (
                <p className="text-sm text-ink-muted">
                  Sin audiencias programadas. El despacho le avisará en cuanto
                  se fije una.
                </p>
              )}
            </Card>
          </section>

          {/* --- Deadlines ------------------------------------------------ */}
          {deadlines.length > 0 ? (
            <section className="rise" style={{ animationDelay: "260ms" }}>
              <SectionHeading eyebrow="Plazos" title="Próximos vencimientos" />
              <Card className="mt-5 p-5">
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
              </Card>
            </section>
          ) : null}

          {/* --- Evidence available --------------------------------------- */}
          {evidences.length > 0 ? (
            <section className="rise" style={{ animationDelay: "320ms" }}>
              <SectionHeading eyebrow="Prueba" title="Evidencias visibles" />
              <Card className="mt-5 p-5">
                <ul className="space-y-4">
                  {evidences.slice(0, 5).map((item) => (
                    <li key={item.id} className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-ink">{item.title}</p>
                        <p className="text-xs text-ink-muted">
                          {formatDate(item.created_at)}
                        </p>
                      </div>
                      <Chip tone={evidenceStatusTone(item.status)}>
                        {evidenceStatusLabel(item.status)}
                      </Chip>
                    </li>
                  ))}
                </ul>
                <p className="mt-5 border-t border-rule pt-4 text-xs leading-relaxed text-ink-faint">
                  Las evidencias se muestran en la versión preparada para su
                  consulta. Los originales los conserva el despacho.
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
          <p className="font-display mt-0.5 text-xl leading-snug text-ink">
            {item.title}
          </p>
        </div>
        <Chip tone={caseStatusTone(item.status)}>{item.status}</Chip>
      </div>
      <p className="mt-2 text-xs text-ink-faint">
        Abierto el {formatDate(item.opened_at)}
      </p>
    </Link>
  );
}

function Stat({
  value,
  label,
  tone,
  index,
}: {
  value: number;
  label: string;
  tone: "ink" | "forest" | "brass" | "wax";
  index: number;
}) {
  const toneClass = {
    ink: "text-ink",
    forest: "text-forest",
    brass: "text-brass",
    wax: "text-wax",
  }[tone];

  return (
    <div
      className="rise bg-surface px-5 py-6"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <p className={`font-display text-4xl leading-none ${toneClass}`}>{value}</p>
      <p className="label-rule mt-2">{label}</p>
    </div>
  );
}
