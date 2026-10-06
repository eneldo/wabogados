import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import {
  DeactivateLawyerButton,
  LawyerForm,
} from "@/components/admin/abogados/lawyer-form";
import { PageHeader } from "@/components/admin/page-furniture";
import { Card, EmptyState, Label, SectionHeading } from "@/components/primitives";
import { deactivateLawyer, updateLawyer } from "@/features/abogados/actions";
import { ApiNotAuthenticated, apiFetch, ApiRequestError } from "@/lib/api";
import { formatDateTime, humanise } from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type { LawyerRecord, LegalAreaOption } from "@/lib/types";

/**
 * One lawyer.
 *
 * The change history is here for the same reason it is on the client screen: a
 * professional card number or a suspension that nobody can trace is a problem
 * waiting for an audit.
 */

type ChangeLog = {
  id: string;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  changed_by: string | null;
  created_at: string;
};

const FIELD_NAMES: Record<string, string> = {
  full_name: "Nombre",
  professional_card: "Tarjeta profesional",
  email: "Correo electrónico",
  phone: "Teléfono",
  status: "Estado",
  photo_url: "Fotografía",
  specialties: "Especialidades",
  legal_areas: "Áreas jurídicas",
};

export default async function LawyerDetailPage({
  params,
}: {
  params: Promise<{ lawyerId: string }>;
}) {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") redirect("/admin/abogados");

  const { lawyerId } = await params;

  let lawyer: LawyerRecord;
  try {
    lawyer = await apiFetch<LawyerRecord>(`/api/v1/lawyers/${lawyerId}`);
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) redirect("/login");
    if (error instanceof ApiRequestError && (error.isNotFound || error.isForbidden)) {
      notFound();
    }
    throw error;
  }

  const [history, areas] = await Promise.all([
    apiFetch<ChangeLog[]>(`/api/v1/lawyers/${lawyerId}/history`, {
      query: { limit: 40 },
    }).catch(() => [] as ChangeLog[]),
    apiFetch<LegalAreaOption[]>("/api/v1/lawyers/legal-areas").catch(
      () => [] as LegalAreaOption[],
    ),
  ]);

  return (
    <div>
      <PageHeader
        eyebrow={humanise(lawyer.status)}
        title={lawyer.full_name}
        description={`Documento ${lawyer.document_type} ${lawyer.document_number}. Alta el ${formatDateTime(lawyer.created_at)}.`}
        actions={
          lawyer.is_active ? (
            <DeactivateLawyerButton
              action={deactivateLawyer}
              lawyerId={lawyer.id}
              lawyerName={lawyer.full_name}
            />
          ) : (
            <p className="rounded-card border border-rule-strong bg-surface px-3.5 py-2 text-xs uppercase tracking-[0.12em] text-ink-muted">
              Desactivado
            </p>
          )
        }
      />

      <p className="mt-4 text-xs">
        <Link
          href="/admin/abogados"
          className="font-semibold uppercase tracking-[0.12em] text-wax underline-offset-4 hover:underline"
        >
          ← Volver al listado
        </Link>
      </p>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1.35fr_1fr]">
        <section>
          <SectionHeading eyebrow="Ficha" title="Datos del profesional" />
          <Card className="mt-5 p-6">
            <LawyerForm
              key={`${lawyer.id}-${lawyer.updated_at}`}
              action={updateLawyer}
              lawyer={lawyer}
              areas={areas}
            />
          </Card>
        </section>

        <section>
          <SectionHeading eyebrow="Trazabilidad" title="Historial de cambios" />
          <div className="mt-5">
            {history.length === 0 ? (
              <EmptyState
                title="Sin cambios registrados"
                hint="Cada modificación guardada desde aquí queda anotada con su autor y su fecha."
              />
            ) : (
              <ol className="space-y-3">
                {history.map((entry) => (
                  <li
                    key={entry.id}
                    className="rounded-card border border-rule bg-surface px-4 py-3"
                  >
                    <p className="text-sm font-medium text-ink">
                      {FIELD_NAMES[entry.field_name] ?? humanise(entry.field_name)}
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-ink-muted">
                      {entry.old_value ? (
                        <>
                          <span className="line-through opacity-60">{entry.old_value}</span>
                          {" → "}
                        </>
                      ) : null}
                      <span>{entry.new_value ?? "—"}</span>
                    </p>
                    <p className="tnum mt-1.5 text-[0.6875rem] text-ink-faint">
                      {formatDateTime(entry.created_at)}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <Card className="mt-6 p-5">
            <Label>Identificador</Label>
            <p className="tnum mt-1.5 break-all text-xs text-ink-muted">{lawyer.id}</p>
            <Label>Usuario vinculado</Label>
            <p className="tnum mt-1.5 break-all text-xs text-ink-muted">
              {lawyer.user_id ?? "Sin cuenta de acceso"}
            </p>
          </Card>
        </section>
      </div>
    </div>
  );
}