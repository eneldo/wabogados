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
import { ServiceUnavailable } from "@/components/service-unavailable";
import {
  caseStatusTone,
  evidenceStatusLabel,
  evidenceStatusTone,
  formatDate,
  formatWhen,
  proceduralStageLabel,
  visibilityLabel,
  visibilityTone,
} from "@/lib/format";
import { loadForSession, requireSession } from "@/lib/session-guard";
import type { DashboardHearing, Evidence } from "@/lib/types";

/**
 * One file, seen whole.
 *
 * A client asking "how is my case going" wants the file, not a menu: what stage
 * it is in, what is published, what the court has set, and what they still owe
 * a reply to. Everything here comes from the scoped endpoints, so a client
 * outside the file never reaches this page at all — the API answers 404 and so
 * does this one.
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

  const { value: evidences, failed } = await loadForSession<Evidence[]>(
    `/api/v1/cases/${caseId}/evidences`,
  );
  if (failed) return <ServiceUnavailable />;

  // The dashboard carries the case header fields, so a case outside the caller's
  // scope never appears in it and this page reports 404 rather than an empty file.
  const { value: dashboard } = await loadForSession<{
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
  }>("/api/v1/dashboard", { query: { limit: 50 } });

  const summary = dashboard?.cases.find((item) => item.id === caseId);
  if (!summary) notFound();

  const hearings = (dashboard?.hearings ?? []).filter(
    (item) => item.case_id === caseId,
  );
  const deadlines = (dashboard?.deadlines ?? []).filter(
    (item) => item.case_id === caseId,
  );

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
          </div>
          <Chip tone={caseStatusTone(summary.status)}>
            {summary.status === "abierto" ? "En curso" : summary.status}
          </Chip>
        </div>
      </header>

      <div className="mt-10 grid gap-10 lg:grid-cols-[1.35fr_1fr]">
        <div className="space-y-10">
          <section className="rise" style={{ animationDelay: "60ms" }}>
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
            <section className="rise" style={{ animationDelay: "180ms" }}>
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
