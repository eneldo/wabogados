"use client";

import { useActionState, useEffect, useRef } from "react";

import {
  createClientRequest,
  updateClientRequest,
} from "@/features/expedientes/actions";
import {
  Button,
  FormField,
  FormStatus,
  SelectInput,
  TextArea,
  TextInput,
} from "@/components/admin/form-controls";
import { Card, Chip, EmptyState, SectionHeading } from "@/components/primitives";
import {
  clientRequestStatusLabel,
  clientRequestStatusTone,
  clientRequestTypeLabel,
  formatDate,
  formatDateTime,
} from "@/lib/format";
import type { ActionState, ClientRequestRecord } from "@/lib/types";

const IDLE: ActionState = { status: "idle" };

function toDateInput(value: string | null): string {
  if (!value) return "";
  return value.slice(0, 10);
}

function CreateRequestDialog({ caseId }: { caseId: string }) {
  const [state, formAction, pending] = useActionState(createClientRequest, IDLE);
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (state.status === "ok" && ref.current?.open) ref.current.close();
  }, [state]);
  return (
    <>
      <Button type="button" variant="primary" onClick={() => ref.current?.showModal()}>
        Nueva solicitud
      </Button>
      <dialog
        ref={ref}
        aria-label="Crear solicitud al cliente"
        className="w-[min(36rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <form action={formAction} className="max-h-[85vh] overflow-y-auto p-6">
          <input type="hidden" name="case_id" value={caseId} />
          <h2 className="font-display text-xl">Solicitud al cliente</h2>
          <p className="mt-2 text-sm text-ink-muted">
            El cliente la verá en su portal y recibirá una notificación.
          </p>
          <div className="mt-5 space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Tipo" name="request_type" idPrefix="cr-new" required>
                {(props) => (
                  <SelectInput {...props} defaultValue="documento">
                    <option value="documento">Documento</option>
                    <option value="informacion">Información</option>
                    <option value="tarea">Tarea</option>
                  </SelectInput>
                )}
              </FormField>
              <FormField label="Prioridad" name="priority" idPrefix="cr-new">
                {(props) => (
                  <SelectInput {...props} defaultValue="normal">
                    <option value="normal">Normal</option>
                    <option value="alta">Alta</option>
                    <option value="urgente">Urgente</option>
                  </SelectInput>
                )}
              </FormField>
            </div>
            <FormField label="Título" name="title" idPrefix="cr-new" required error={state.errors?.title}>
              {(props) => <TextInput {...props} required minLength={3} maxLength={255} />}
            </FormField>
            <FormField label="Descripción / instrucciones" name="description" idPrefix="cr-new">
              {(props) => <TextArea {...props} rows={3} maxLength={4000} />}
            </FormField>
            <FormField label="Fecha límite" name="due_at" idPrefix="cr-new" hint="Opcional. Se mostrará como vencimiento al cliente.">
              {(props) => <TextInput {...props} type="date" />}
            </FormField>
            <FormStatus state={state} />
          </div>
          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => ref.current?.close()}>Cancelar</Button>
            <Button type="submit" variant="primary" pending={pending}>Crear solicitud</Button>
          </div>
        </form>
      </dialog>
    </>
  );
}

function UpdateRequestDialog({ caseId, item }: { caseId: string; item: ClientRequestRecord }) {
  const [state, formAction, pending] = useActionState(updateClientRequest, IDLE);
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (state.status === "ok" && ref.current?.open) ref.current.close();
  }, [state]);
  const idp = `cr-${item.id}`;
  return (
    <>
      <Button type="button" variant="quiet" onClick={() => ref.current?.showModal()}>
        Gestionar
      </Button>
      <dialog
        ref={ref}
        aria-label={`Gestionar solicitud ${item.title}`}
        className="w-[min(38rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <form action={formAction} className="max-h-[85vh] overflow-y-auto p-6">
          <input type="hidden" name="case_id" value={caseId} />
          <input type="hidden" name="request_id" value={item.id} />
          <h2 className="font-display text-xl">Gestionar solicitud</h2>
          <div className="mt-5 space-y-4">
            <FormField label="Estado" name="status" idPrefix={idp}>
              {(props) => (
                <SelectInput {...props} defaultValue={item.status}>
                  <option value="pendiente">Pendiente</option>
                  <option value="respondida">Respondida</option>
                  <option value="revisada">Revisada</option>
                  <option value="cancelada">Cancelada</option>
                </SelectInput>
              )}
            </FormField>
            <FormField label="Título" name="title" idPrefix={idp}>
              {(props) => <TextInput {...props} defaultValue={item.title} maxLength={255} />}
            </FormField>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Tipo" name="request_type" idPrefix={idp}>
                {(props) => (
                  <SelectInput {...props} defaultValue={item.request_type}>
                    <option value="documento">Documento</option>
                    <option value="informacion">Información</option>
                    <option value="tarea">Tarea</option>
                  </SelectInput>
                )}
              </FormField>
              <FormField label="Prioridad" name="priority" idPrefix={idp}>
                {(props) => (
                  <SelectInput {...props} defaultValue={item.priority}>
                    <option value="normal">Normal</option>
                    <option value="alta">Alta</option>
                    <option value="urgente">Urgente</option>
                  </SelectInput>
                )}
              </FormField>
            </div>
            <FormField label="Fecha límite" name="due_at" idPrefix={idp}>
              {(props) => <TextInput {...props} type="date" defaultValue={toDateInput(item.due_at)} />}
            </FormField>
            <FormField label="Descripción" name="description" idPrefix={idp}>
              {(props) => <TextArea {...props} rows={3} defaultValue={item.description ?? ""} />}
            </FormField>
            {item.response_text ? (
              <div className="rounded-md border border-rule bg-paper/60 px-3 py-3">
                <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.1em] text-ink-faint">Respuesta del cliente</p>
                <p className="mt-1 text-sm text-ink">{item.response_text}</p>
                {item.responded_at ? <p className="mt-1 text-xs text-ink-muted">{formatDateTime(item.responded_at)}</p> : null}
              </div>
            ) : null}
            <FormField label="Nota de revisión interna" name="review_note" idPrefix={idp}>
              {(props) => <TextArea {...props} rows={2} defaultValue={item.review_note ?? ""} maxLength={2000} />}
            </FormField>
            <FormStatus state={state} />
          </div>
          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => ref.current?.close()}>Cancelar</Button>
            <Button type="submit" variant="primary" pending={pending}>Guardar</Button>
          </div>
        </form>
      </dialog>
    </>
  );
}

export function ClientRequestsPanel({
  caseId,
  items,
}: {
  caseId: string;
  items: ClientRequestRecord[];
}) {
  return (
    <section>
      <SectionHeading
        eyebrow="Cliente"
        title="Solicitudes y tareas"
        action={<CreateRequestDialog caseId={caseId} />}
      />
      <p className="mt-2 text-sm text-ink-muted">
        Solicitudes de documentos, información o tareas con vencimiento. El cliente responde desde su portal.
      </p>
      {items.length === 0 ? (
        <div className="mt-5">
          <EmptyState title="Sin solicitudes" hint="Cree una solicitud cuando necesite que el cliente entregue algo o complete una tarea." />
        </div>
      ) : (
        <Card className="mt-5 overflow-hidden">
          <ul className="divide-y divide-rule">
            {items.map((item) => (
              <li key={item.id} className="px-5 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Chip tone={clientRequestStatusTone(item.status)} dot>{clientRequestStatusLabel(item.status)}</Chip>
                      <Chip tone="neutral" dot>{clientRequestTypeLabel(item.request_type)}</Chip>
                      {item.is_overdue ? <Chip tone="wax">Vencida</Chip> : null}
                    </div>
                    <p className="mt-2 font-medium text-ink">{item.title}</p>
                    {item.description ? <p className="mt-1 text-sm text-ink-muted">{item.description}</p> : null}
                    <p className="mt-1 text-xs text-ink-faint">
                      {item.due_at ? `Vence: ${formatDate(item.due_at)}` : "Sin vencimiento"}
                      {item.responded_at ? ` · Respondida: ${formatDateTime(item.responded_at)}` : ""}
                    </p>
                  </div>
                  <UpdateRequestDialog caseId={caseId} item={item} />
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </section>
  );
}
