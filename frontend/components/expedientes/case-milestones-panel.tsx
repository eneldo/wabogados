"use client";

import { useActionState, useEffect, useRef } from "react";

import {
  createCaseMilestone,
  updateCaseMilestone,
} from "@/features/expedientes/actions";
import {
  Button,
  CheckField,
  FormField,
  FormStatus,
  SelectInput,
  TextArea,
  TextInput,
} from "@/components/admin/form-controls";
import { Card, Chip, EmptyState, SectionHeading } from "@/components/primitives";
import { formatDate, milestoneStatusLabel, milestoneStatusTone } from "@/lib/format";
import type { ActionState, CaseMilestoneRecord } from "@/lib/types";

const IDLE: ActionState = { status: "idle" };

function toDateInput(value: string | null): string {
  if (!value) return "";
  return value.slice(0, 10);
}

function MilestoneFields({
  idPrefix,
  item,
  state,
}: {
  idPrefix: string;
  item?: CaseMilestoneRecord;
  state: ActionState;
}) {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Clave de etapa" name="stage_key" idPrefix={idPrefix} hint="Identificador corto, ej. admision, pruebas, sentencia.">
          {(props) => <TextInput {...props} defaultValue={item?.stage_key ?? ""} maxLength={50} />}
        </FormField>
        <FormField label="Orden" name="sort_order" idPrefix={idPrefix}>
          {(props) => <TextInput {...props} type="number" defaultValue={String(item?.sort_order ?? 0)} />}
        </FormField>
      </div>
      <FormField label="Título" name="title" idPrefix={idPrefix} required error={state.errors?.title}>
        {(props) => <TextInput {...props} required minLength={2} maxLength={255} defaultValue={item?.title ?? ""} />}
      </FormField>
      <FormField label="Estado" name="status" idPrefix={idPrefix}>
        {(props) => (
          <SelectInput {...props} defaultValue={item?.status ?? "pendiente"}>
            <option value="pendiente">Pendiente</option>
            <option value="en_curso">En curso</option>
            <option value="completado">Completado</option>
          </SelectInput>
        )}
      </FormField>
      <FormField label="Descripción" name="description" idPrefix={idPrefix}>
        {(props) => <TextArea {...props} rows={3} maxLength={4000} defaultValue={item?.description ?? ""} />}
      </FormField>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Fecha prevista" name="planned_at" idPrefix={idPrefix}>
          {(props) => <TextInput {...props} type="date" defaultValue={toDateInput(item?.planned_at ?? null)} />}
        </FormField>
        <FormField label="Fecha completada" name="completed_at" idPrefix={idPrefix}>
          {(props) => <TextInput {...props} type="date" defaultValue={toDateInput(item?.completed_at ?? null)} />}
        </FormField>
      </div>
      <div className="rounded-md border border-rule bg-paper/40 px-3 py-3">
        <CheckField
          name="is_published"
          defaultChecked={item?.is_published ?? false}
          label="Publicado al portal del cliente"
          hint="Control de publicación: si está activo, el cliente podrá ver este hito. Al publicar se notifica al cliente."
        />
      </div>
    </>
  );
}

function CreateMilestoneDialog({ caseId }: { caseId: string }) {
  const [state, formAction, pending] = useActionState(createCaseMilestone, IDLE);
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (state.status === "ok" && ref.current?.open) ref.current.close();
  }, [state]);
  return (
    <>
      <Button type="button" variant="primary" onClick={() => ref.current?.showModal()}>
        Nuevo hito
      </Button>
      <dialog
        ref={ref}
        aria-label="Crear hito de etapa"
        className="w-[min(38rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <form action={formAction} className="max-h-[85vh] overflow-y-auto p-6">
          <input type="hidden" name="case_id" value={caseId} />
          <h2 className="font-display text-xl">Hito / etapa del caso</h2>
          <p className="mt-2 text-sm text-ink-muted">
            Defina la etapa y decida si se publica al cliente. La publicación es controlada.
          </p>
          <div className="mt-5 space-y-4">
            <MilestoneFields idPrefix="cm-new" state={state} />
            <FormStatus state={state} />
          </div>
          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => ref.current?.close()}>Cancelar</Button>
            <Button type="submit" variant="primary" pending={pending}>Guardar hito</Button>
          </div>
        </form>
      </dialog>
    </>
  );
}

function UpdateMilestoneDialog({ caseId, item }: { caseId: string; item: CaseMilestoneRecord }) {
  const [state, formAction, pending] = useActionState(updateCaseMilestone, IDLE);
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (state.status === "ok" && ref.current?.open) ref.current.close();
  }, [state]);
  const idp = `cm-${item.id}`;
  return (
    <>
      <Button type="button" variant="quiet" onClick={() => ref.current?.showModal()}>
        Editar
      </Button>
      <dialog
        ref={ref}
        aria-label={`Editar hito ${item.title}`}
        className="w-[min(38rem,calc(100vw-2rem))] rounded-card border border-rule-strong bg-surface p-0 backdrop:bg-ink/45"
      >
        <form action={formAction} className="max-h-[85vh] overflow-y-auto p-6">
          <input type="hidden" name="case_id" value={caseId} />
          <input type="hidden" name="milestone_id" value={item.id} />
          <h2 className="font-display text-xl">Editar hito</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            <Chip tone={item.is_published ? "forest" : "neutral"}>
              {item.is_published ? "Publicado al portal" : "No publicado (interno)"}
            </Chip>
          </div>
          <div className="mt-5 space-y-4">
            <MilestoneFields idPrefix={idp} item={item} state={state} />
            <FormStatus state={state} />
          </div>
          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => ref.current?.close()}>Cancelar</Button>
            <Button type="submit" variant="primary" pending={pending}>Guardar cambios</Button>
          </div>
        </form>
      </dialog>
    </>
  );
}

export function CaseMilestonesPanel({
  caseId,
  items,
}: {
  caseId: string;
  items: CaseMilestoneRecord[];
}) {
  return (
    <section>
      <SectionHeading
        eyebrow="Progreso"
        title="Hitos y etapas"
        action={<CreateMilestoneDialog caseId={caseId} />}
      />
      <p className="mt-2 text-sm text-ink-muted">
        Etapas del expediente con <strong>publicación controlada</strong>. Solo los hitos publicados son visibles para el cliente.
      </p>
      {items.length === 0 ? (
        <div className="mt-5">
          <EmptyState title="Sin hitos definidos" hint="Cree hitos para comunicar el avance por etapas. Marque “Publicado al portal” solo cuando desee que el cliente lo vea." />
        </div>
      ) : (
        <Card className="mt-5 overflow-hidden">
          <ol className="divide-y divide-rule">
            {items.map((item, index) => (
              <li key={item.id} className="px-5 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[0.6875rem] font-semibold uppercase tracking-[0.1em] text-ink-faint">Etapa {index + 1}</span>
                      <Chip tone={milestoneStatusTone(item.status)} dot>{milestoneStatusLabel(item.status)}</Chip>
                      <Chip tone={item.is_published ? "forest" : "neutral"} dot>
                        {item.is_published ? "Publicado" : "Interno"}
                      </Chip>
                    </div>
                    <p className="mt-1.5 font-medium text-ink">{item.title}</p>
                    {item.stage_key ? <p className="mt-0.5 text-xs text-ink-faint">Clave: {item.stage_key}</p> : null}
                    {item.description ? <p className="mt-1 text-sm text-ink-muted">{item.description}</p> : null}
                    <p className="mt-1 text-xs text-ink-faint">
                      {item.completed_at ? `Completada: ${formatDate(item.completed_at)}` : item.planned_at ? `Prevista: ${formatDate(item.planned_at)}` : "Sin fechas"}
                      {item.published_at ? ` · Publicada: ${formatDate(item.published_at)}` : ""}
                    </p>
                  </div>
                  <UpdateMilestoneDialog caseId={caseId} item={item} />
                </div>
              </li>
            ))}
          </ol>
        </Card>
      )}
    </section>
  );
}
