import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import {
  ClientForm,
  DeactivateButton,
} from "@/components/admin/clientes/client-form";
import { PageHeader } from "@/components/admin/page-furniture";
import { Card, Chip, EmptyState, Label, SectionHeading } from "@/components/primitives";
import { deactivateClient, updateClient } from "@/features/clientes/actions";
import { ApiNotAuthenticated, apiFetch, ApiRequestError } from "@/lib/api";
import { formatDateTime, humanise } from "@/lib/format";
import { requireSession } from "@/lib/session-guard";
import type { ClientRecord } from "@/lib/types";

/**
 * One client.
 *
 * The edit form and the change history sit on the same screen on purpose. A
 * form without the history of what was changed is a form that quietly loses
 * information, and the history is what tells an administrator whether a phone
 * number was wrong from the start or was corrected last week.
 *
 * `document_type` and `document_number` are not editable here and the screen
 * says why. Changing a client's identity document does not edit a person; it
 * makes a different person out of the row, and it belongs in a deliberate
 * decision rather than a text field.
 */

type ChangeLog = {
  id: string;
  entity: string;
  entity_id: string;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  changed_by: string | null;
  created_at: string;
};

const FIELD_NAMES: Record<string, string> = {
  full_name: "Nombre",
  legal_name: "Razón social",
  commercial_name: "Nombre comercial",
  email: "Correo electrónico",
  phone: "Teléfono",
  address: "Dirección",
  notes: "Notas",
  client_type: "Tipo de cliente",
  document_type: "Tipo de documento",
  document_number: "Número de documento",
};

export default async function ClientDetailPage({
  params,
}: {
  params: Promise<{ clientId: string }>;
}) {
  const session = await requireSession();
  if (session.kind === "unauthenticated") redirect("/login");
  if (session.kind === "unavailable") redirect("/admin/clientes");

  const { clientId } = await params;

  let client: ClientRecord;
  try {
    client = await apiFetch<ClientRecord>(`/api/v1/clients/${clientId}`);
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) redirect("/login");
    // A 403 is not a 404 here: the record exists and this person may not see
    // it. The message differs, the address does not.
    if (error instanceof ApiRequestError && (error.isNotFound || error.isForbidden)) {
      notFound();
    }
    throw error;
  }

  const history = await apiFetch<ChangeLog[]>(
    `/api/v1/clients/${clientId}/history`,
    { query: { limit: 40 } },
  ).catch(() => [] as ChangeLog[]);

  return (
    <div>
      <PageHeader
        eyebrow={client.client_type === "juridica" ? "Persona jurídica" : "Persona natural"}
        title={client.display_name}
        description={`Documento ${client.document_type} ${client.document_number}. Alta el ${formatDateTime(client.created_at)}.`}
        actions={
          client.is_active ? (
            <DeactivateButton
              action={deactivateClient}
              clientId={client.id}
              clientName={client.display_name}
            />
          ) : (
            <Chip tone="ink">Cliente inactivo</Chip>
          )
        }
      />

      <p className="mt-4 text-xs">
        <Link
          href="/admin/clientes"
          className="font-semibold uppercase tracking-[0.12em] text-wax underline-offset-4 hover:underline"
        >
          ← Volver al listado
        </Link>
      </p>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1.35fr_1fr]">
        <section>
          <SectionHeading
            eyebrow="Ficha"
            title="Datos del cliente"
            action={
              <p className="max-w-xs text-xs text-ink-faint">
                El documento que identifica al cliente no se edita aquí: cambiarlo
                convierte el registro en otra persona.
              </p>
            }
          />
          <Card className="mt-5 p-6">
            <ClientForm
              key={`${client.id}-${client.updated_at}`}
              action={updateClient}
              client={client}
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
            <p className="tnum mt-1.5 break-all text-xs text-ink-muted">
              {client.id}
            </p>
            {client.user_id ? (
              <>
                <Label>Usuario vinculado</Label>
                <p className="tnum mt-1.5 break-all text-xs text-ink-muted">
                  {client.user_id}
                </p>
              </>
            ) : (
              <>
                <Label>Usuario vinculado</Label>
                <p className="mt-1.5 text-xs text-ink-faint">
                  Sin vincular. Un cliente sin cuenta no puede entrar al portal.
                </p>
              </>
            )}
          </Card>
        </section>
      </div>

      <p className="mt-10 border-t border-rule pt-5 text-xs text-ink-faint">
        Este registro se conserva aunque el cliente deje de serlo. Sus expedientes,
        documentos y evidencias no dependen de que siga activo.
      </p>
    </div>
  );
}