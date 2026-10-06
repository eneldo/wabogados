import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import {
  AddPartyButton,
  AssignLawyerButton,
  CaseForm,
  CloseCaseButton,
} from "@/components/admin/expedientes/case-form";
import { PageHeader } from "@/components/admin/page-furniture";
import { Chip } from "@/components/primitives";
import {
  Card,
  EmptyState,
  Label,
  SectionHeading,
} from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import {
  addParty,
  assignLawyer,
  closeCase,
  updateCase,
} from "@/features/expedientes/actions";
import { ApiNotAuthenticated, apiFetch, ApiRequestError } from "@/lib/api";
import {
  caseStatusLabel,
  caseStatusTone,
  formatDate,
  formatMoney,
  humanise,
  partyRoleLabel,
  priorityLabel,
  priorityTone,
  processTypeLabel,
} from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type { Case360, CaseOption, LegalAreaOption } from "@/lib/types";

/**
 * The 360 view of one case.
 *
 * It reads `GET /cases/{id}/360`, which is the endpoint built for exactly this
 * screen: the case, its collaborators, its parties and a count for every
 * section. The counts are what this page is really for — a lawyer opening a
 * file needs to know at a glance whether it has documents, evidences and a
 * hearing waiting, and fetching five lists to find out is five round trips and
 * five chances to render a half-loaded screen.
 *
 * Sections the backend marks `available: false` are shown as such. An empty
 * section and a section the API could not read are different, and this page says
 * which one it is looking at.
 */

export default async function CaseDetailPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} backHref="/admin/expedientes" />;
  }

  const { caseId } = await params;

  let view: Case360;
  try {
    view = await apiFetch<Case360>(`/api/v1/cases/${caseId}/360`);
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) redirect("/login");
    if (error instanceof ApiRequestError && (error.isNotFound || error.isForbidden)) {
      notFound();
    }
    throw error;
  }

  const record = view.case;
  const isOpen = record.status !== "cerrado" && record.status !== "archivado";

  const [clients, lawyers, areas] = await Promise.all([
    apiFetch<{ items: Array<{ id: string; display_name: string }> }>(
      "/api/v1/clients",
      { query: { skip: 0, limit: 200, include_inactive: 1 } },
    ).catch(() => ({ items: [] })),
    apiFetch<{ items: Array<{ id: string; full_name: string }> }>(
      "/api/v1/lawyers",
      { query: { skip: 0, limit: 200, status: "activo" } },
    ).catch(() => ({ items: [] })),
    apiFetch<LegalAreaOption[]>("/api/v1/lawyers/legal-areas").catch(() => []),
  ]);

  const toOption = (items: Array<{ id: string; label: string }>): CaseOption[] => items;

  const clientOptions = toOption(
    clients.items.map((c) => ({ id: c.id, label: c.display_name })),
  );
  const lawyerOptions = toOption(
    lawyers.items.map((l) => ({ id: l.id, label: l.full_name })),
  );
  const areaOptions = toOption(areas.map((a) => ({ id: a.id, label: a.name })));

  const sections = [
    { key: "actuaciones", label: "Actuaciones", total: view.actuaciones_total },
    { key: "agenda", label: "Agenda", total: view.agenda_total },
    { key: "audiencias", label: "Audiencias", total: view.audiencias_total },
    { key: "documentos", label: "Documentos", total: view.documentos_total },
    { key: "evidencias", label: "Evidencias", total: view.evidencias_total },
  ] as const;

  return (
    <div>
      <PageHeader
        eyebrow={record.case_number}
        title={record.title}
        description={
          record.closed_at
            ? `Cerrado el ${formatDate(record.closed_at)}. No se borra: se conserva íntegro y cualquier corrección posterior queda registrada en la auditoría.`
            : `Abierto el ${formatDate(record.opened_at)} · ${processTypeLabel(record.process_type)}`
        }
        actions={
          isOpen ? (
            <CloseCaseButton
              action={closeCase}
              caseId={record.id}
              caseNumber={record.case_number}
            />
          ) : (
            <Chip tone="ink">{caseStatusLabel(record.status)}</Chip>
          )
        }
      />

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <Chip tone={caseStatusTone(record.status)}>
          {caseStatusLabel(record.status)}
        </Chip>
        <Chip tone={priorityTone(record.priority)} dot>
          Prioridad {priorityLabel(record.priority).toLowerCase()}
        </Chip>
        {record.legal_area_name ? <Chip>{record.legal_area_name}</Chip> : null}
        <Link
          href={`/expedientes/${record.id}/evidencias`}
          className="ml-1 text-xs font-semibold uppercase tracking-[0.1em] text-wax underline-offset-4 hover:underline"
        >
          Gestor de evidencias →
        </Link>
      </div>

      <p className="mt-4 text-xs">
        <Link
          href="/admin/expedientes"
          className="font-semibold uppercase tracking-[0.12em] text-wax underline-offset-4 hover:underline"
        >
          ← Volver al listado
        </Link>
      </p>

      <div className="mt-9 grid gap-10 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-10">
          <section>
            <SectionHeading eyebrow="Ficha" title="Datos del expediente" />
            <Card className="mt-5 p-6">
              <CaseForm
                /* Remount on every server-side change. React does not touch the
                 * value of an uncontrolled <select>, so after a save the form
                 * kept the pre-edit option while the page around it already
                 * showed the new state. `updated_at` is the version the server
                 * bumps on every write, so it is the honest key. */
                key={`${record.id}-${record.updated_at}`}
                action={updateCase}
                record={record}
                clients={clientOptions}
                lawyers={lawyerOptions}
                areas={areaOptions}
              />
            </Card>
          </section>

          <section>
            <SectionHeading
              eyebrow="Equipo"
              title="Responsables"
              action={
                <AssignLawyerButton
                  action={assignLawyer}
                  caseId={record.id}
                  lawyers={lawyerOptions}
                />
              }
            />
            <div className="mt-5 space-y-4">
              <Card className="p-5">
                <Label>Responsable</Label>
                <p className="mt-1.5 text-sm text-ink">
                  {record.responsible_lawyer_name ?? "Sin asignar"}
                </p>
              </Card>

              {view.collaborators.length === 0 ? (
                <p className="text-sm text-ink-faint">
                  Sin colaboradores incorporados.
                </p>
              ) : (
                <ul className="divide-y divide-rule border-y border-rule">
                  {view.collaborators.map((person) => (
                    <li
                      key={person.lawyer_id}
                      className="flex items-center justify-between gap-4 py-3"
                    >
                      <span className="text-sm text-ink">{person.lawyer_name}</span>
                      <span className="text-xs text-ink-muted">
                        {humanise(person.role)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <section>
            <SectionHeading
              eyebrow="Proceso"
              title="Partes"
              action={
                <AddPartyButton
                  action={addParty}
                  caseId={record.id}
                  clients={clientOptions}
                />
              }
            />
            <div className="mt-5">
              {view.parties.length === 0 ? (
                <EmptyState
                  title="Sin partes registradas"
                  hint="Un expediente se lee mucho mejor con las partes anotadas: quién reclama, quién responde."
                />
              ) : (
                <table className="ledger">
                  <caption className="sr-only">Partes del expediente</caption>
                  <thead>
                    <tr>
                      <th scope="col" className="label-rule">
                        Nombre
                      </th>
                      <th scope="col" className="label-rule">
                        Papel
                      </th>
                      <th scope="col" className="label-rule">
                        Documento
                      </th>
                      <th scope="col" className="label-rule">
                        Origen
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {view.parties.map((party) => (
                      <tr key={party.id}>
                        <th scope="row" className="py-3 pr-4 font-normal">
                          <span className="text-sm text-ink">{party.name}</span>
                          {party.notes ? (
                            <span className="mt-0.5 block text-xs text-ink-faint">
                              {party.notes}
                            </span>
                          ) : null}
                        </th>
                        <td className="py-3 pr-4 text-xs text-ink-muted">
                          {partyRoleLabel(party.party_role)}
                        </td>
                        <td className="tnum py-3 pr-4 text-xs text-ink-muted">
                          {party.document_number
                            ? `${party.document_type ?? ""} ${party.document_number}`
                            : "—"}
                        </td>
                        <td className="py-3 pr-4 text-xs">
                          {party.is_external ? (
                            <Chip>Externa</Chip>
                          ) : (
                            <Chip tone="forest">Cliente</Chip>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>
        </div>

        <aside className="space-y-6">
          <Card className="p-5">
            <Label>Resumen</Label>
            <dl className="mt-3 space-y-3 text-sm">
              <Row term="Cliente" value={record.client_name} />
              <Row term="Tipo de proceso" value={processTypeLabel(record.process_type)} />
              <Row term="Área jurídica" value={record.legal_area_name ?? "Sin clasificar"} />
              <Row term="Juzgado" value={record.court ?? "—"} />
              <Row term="Jurisdicción" value={record.jurisdiction ?? "—"} />
              <Row term="Número de proceso" value={record.file_number ?? "—"} />
              <Row term="Cuantía" value={formatMoney(record.amount)} />
              <Row term="Entradas de historial" value={String(view.history_entries)} />
            </dl>
          </Card>

          <Card className="p-5">
            <Label>Contenido</Label>
            <ul className="mt-3 space-y-2.5">
              {sections.map((section) => (
                <li
                  key={section.key}
                  className="flex items-baseline justify-between gap-3 text-sm"
                >
                  <span className="text-ink-muted">{section.label}</span>
                  <span className="tnum font-medium text-ink">
                    {section.total}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-xs leading-relaxed text-ink-faint">
              Las cifras vienen de la ficha 360 y son de lectura, no de cálculo.
              El detalle de cada sección se abre desde su propio módulo.
            </p>
          </Card>

          {isOpen ? (
            <p className="text-xs leading-relaxed text-ink-faint">
              Este expediente puede cerrarse, no borrarse. Cerrarlo conserva
              documentos, evidencias, actuaciones y audiencias, y deja de
              aparecer en el trabajo activo del despacho.
            </p>
          ) : (
            <p className="text-xs leading-relaxed text-ink-faint">
              Expediente cerrado. Sigue siendo consultable y nada de su
              contenido se ha eliminado.
            </p>
          )}

          {/*
            A link, not a button wrapping a link. The evidence manager is a
            destination, and a `<button>` containing an `<a>` is invalid HTML that
            screen readers announce twice.
          */}
          <Link
            href={`/expedientes/${record.id}/evidencias`}
            className="block rounded-card border border-rule-strong bg-surface px-3.5 py-2.5 text-center text-xs font-semibold uppercase tracking-[0.12em] text-ink transition-colors hover:border-wax hover:text-wax"
          >
            Abrir el gestor de evidencias
          </Link>
        </aside>
      </div>
    </div>
  );
}

function Row({ term, value }: { term: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="shrink-0 text-ink-muted">{term}</dt>
      <dd className="text-right text-ink">{value}</dd>
    </div>
  );
}