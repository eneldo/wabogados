import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { Masthead } from "@/components/masthead";
import { Card, Chip, EmptyState, Label, SectionHeading } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { ClientRequestsPanel } from "@/components/expedientes/client-requests-panel";
import { CaseMilestonesPanel } from "@/components/expedientes/case-milestones-panel";
import { ApiNotAuthenticated, ApiRequestError, apiFetch } from "@/lib/api";
import {
  caseStatusLabel,
  caseStatusTone,
  formatDate,
  humanise,
  partyRoleLabel,
  priorityLabel,
  priorityTone,
  processTypeLabel,
} from "@/lib/format";
import { loadForSession, requireSession } from "@/lib/session-guard";
import type {
  Case360,
  CaseMilestoneRecord,
  ClientRequestRecord,
} from "@/lib/types";

/**
 * Staff case detail (non-admin route).
 *
 * Mirrors the admin case detail's management capabilities for client requests and
 * milestones, within the staff layout. Uses the same backend APIs and server actions.
 */
export default async function StaffCaseDetailPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} backHref="/expedientes" />;
  }
  const profile = session.profile;
  const { caseId } = await params;

  let view: Case360;
  try {
    view = await apiFetch<Case360>(`/api/v1/cases/${caseId}/360`);
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) redirect("/login");
    if (error instanceof ApiRequestError && (error.isNotFound || error.isForbidden)) {
      notFound();
    }
    return (
      <Masthead
        eyebrow="WABOGADOS"
        title="Expediente"
        profile={{ name: profile.name, role: profile.roleLabel, unread: profile.unread }}
        nav={[
          { href: "/portal", label: "Panel" },
          { href: "/expedientes", label: "Expedientes" },
          { href: `/expedientes/${caseId}`, label: "Expediente", active: true },
        ]}
      >
        <ServiceUnavailable
          message={error instanceof Error ? error.message : "No fue posible cargar el expediente."}
          backHref="/expedientes"
        />
      </Masthead>
    );
  }

  const [requestsResult, milestonesResult] = await Promise.all([
    loadForSession<ClientRequestRecord[]>(`/api/v1/cases/${caseId}/client-requests`),
    loadForSession<CaseMilestoneRecord[]>(`/api/v1/cases/${caseId}/milestones`),
  ]);
  const clientRequests = requestsResult.value ?? [];
  const milestones = milestonesResult.value ?? [];
  const record = view.case;

  return (
    <Masthead
      eyebrow={record.case_number}
      title={record.title}
      profile={{ name: profile.name, role: profile.roleLabel, unread: profile.unread }}
      nav={[
        { href: "/portal", label: "Panel" },
        { href: "/expedientes", label: "Expedientes" },
        { href: `/expedientes/${caseId}`, label: "Detalle", active: true },
        { href: `/expedientes/${caseId}/evidencias`, label: "Evidencias" },
      ]}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Chip tone={caseStatusTone(record.status)}>{caseStatusLabel(record.status)}</Chip>
        <Chip tone={priorityTone(record.priority)} dot>
          Prioridad {priorityLabel(record.priority).toLowerCase()}
        </Chip>
        {record.legal_area_name ? <Chip>{record.legal_area_name}</Chip> : null}
      </div>

      <p className="mt-4 text-sm text-ink-muted">
        {record.client_name} · {processTypeLabel(record.process_type)} · Abierto {formatDate(record.opened_at)}
      </p>

      <div className="mt-4 flex flex-wrap gap-3 text-xs">
        <Link href="/expedientes" className="font-semibold uppercase tracking-[0.12em] text-wax underline-offset-4 hover:underline">
          ← Volver
        </Link>
        <Link href={`/expedientes/${record.id}/evidencias`} className="font-semibold uppercase tracking-[0.12em] text-wax underline-offset-4 hover:underline">
          Gestor de evidencias →
        </Link>
      </div>

      <div className="mt-9 grid gap-10 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-10">
          <ClientRequestsPanel caseId={record.id} items={clientRequests} />
          <CaseMilestonesPanel caseId={record.id} items={milestones} />

          <section>
            <SectionHeading eyebrow="Proceso" title="Partes" />
            <div className="mt-5">
              {view.parties.length === 0 ? (
                <EmptyState title="Sin partes registradas" hint="Las partes se gestionan desde la ficha administrativa del expediente." />
              ) : (
                <ul className="divide-y divide-rule border-y border-rule">
                  {view.parties.map((party) => (
                    <li key={party.id} className="flex items-center justify-between gap-4 py-3">
                      <span className="text-sm text-ink">{party.name}</span>
                      <span className="text-xs text-ink-muted">{partyRoleLabel(party.party_role)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </div>

        <aside className="space-y-6">
          <Card className="p-5">
            <Label>Resumen</Label>
            <dl className="mt-3 space-y-3 text-sm">
              <div className="flex items-baseline justify-between gap-3"><dt className="shrink-0 text-ink-muted">Responsable</dt><dd className="text-right text-ink">{record.responsible_lawyer_name ?? "Sin asignar"}</dd></div>
              <div className="flex items-baseline justify-between gap-3"><dt className="shrink-0 text-ink-muted">Área</dt><dd className="text-right text-ink">{record.legal_area_name ?? "Sin clasificar"}</dd></div>
              <div className="flex items-baseline justify-between gap-3"><dt className="shrink-0 text-ink-muted">Juzgado</dt><dd className="text-right text-ink">{record.court ?? "—"}</dd></div>
              <div className="flex items-baseline justify-between gap-3"><dt className="shrink-0 text-ink-muted">N° proceso</dt><dd className="text-right text-ink">{record.file_number ?? "—"}</dd></div>
              <div className="flex items-baseline justify-between gap-3"><dt className="shrink-0 text-ink-muted">Colaboradores</dt><dd className="text-right text-ink">{view.collaborators.length}</dd></div>
            </dl>
          </Card>
          {view.collaborators.length > 0 ? (
            <Card className="p-5">
              <Label>Equipo</Label>
              <ul className="mt-3 space-y-2 text-sm">
                {view.collaborators.map((p) => (
                  <li key={p.lawyer_id} className="flex justify-between gap-2">
                    <span className="text-ink">{p.lawyer_name}</span>
                    <span className="text-ink-muted">{humanise(p.role)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}
        </aside>
      </div>
    </Masthead>
  );
}
